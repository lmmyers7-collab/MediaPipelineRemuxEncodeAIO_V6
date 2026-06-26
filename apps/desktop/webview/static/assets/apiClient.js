(function () {
  function readBootstrapElement() {
    if (typeof document === "undefined" || typeof document.getElementById !== "function") return {};
    const element = document.getElementById("media-pipeline-bootstrap");
    if (!element) return {};
    const raw = (element.textContent || "").trim();
    if (!raw) return {};
    try {
      const value = JSON.parse(raw);
      return value && typeof value === "object" ? value : {};
    } catch (_error) {
      return {};
    }
  }

  const bootstrap = Object.assign(
    {},
    readBootstrapElement(),
    window.MEDIA_PIPELINE_BOOTSTRAP || {},
    window.MEDIA_PIPELINE_TAURI_BOOTSTRAP || {}
  );
  const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
  const API_ROUTE_PREFIX = "/api/";
  const apiBase = normalizeApiBase(bootstrap.apiBase || "");
  const token = bootstrap.token || "";
  const DEFAULT_GET_TIMEOUT_MS = 30000;

  function normalizeApiBase(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    let parsed;
    try {
      parsed = new URL(text);
    } catch (_error) {
      throw new Error("API base must be a loopback Local API origin");
    }
    if (
      parsed.protocol !== "http:" ||
      !LOOPBACK_HOSTS.has(parsed.hostname.toLowerCase()) ||
      parsed.pathname !== "/" ||
      parsed.search ||
      parsed.hash
    ) {
      throw new Error("API base must be a loopback Local API origin");
    }
    return parsed.origin;
  }

  function normalizeApiPath(path) {
    const value = String(path || "").trim();
    if (
      !value.startsWith(API_ROUTE_PREFIX) ||
      value.startsWith("//") ||
      /^[A-Za-z][A-Za-z0-9+.-]*:/.test(value) ||
      /[\r\n]/.test(value)
    ) {
      throw new Error("API path must be a local /api/ route");
    }
    return value;
  }

  function bootstrapWithoutToken(value) {
    if (!value || typeof value !== "object") return {};
    const scrubbed = { ...value };
    delete scrubbed.token;
    return scrubbed;
  }

  function scrubBootstrapSecrets() {
    window.MEDIA_PIPELINE_BOOTSTRAP = Object.freeze(bootstrapWithoutToken(bootstrap));
    if (window.MEDIA_PIPELINE_TAURI_BOOTSTRAP && typeof window.MEDIA_PIPELINE_TAURI_BOOTSTRAP === "object") {
      window.MEDIA_PIPELINE_TAURI_BOOTSTRAP = Object.freeze(
        bootstrapWithoutToken(window.MEDIA_PIPELINE_TAURI_BOOTSTRAP)
      );
    }
  }

  scrubBootstrapSecrets();

  function apiHeaders(extraHeaders) {
    const headers = { ...(extraHeaders || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  function invalidJsonError(response, path, raw, error) {
    const route = path || response.url || "API response";
    const status = Number.isFinite(Number(response.status)) ? `HTTP ${response.status}` : "HTTP response";
    const preview = raw.trim().replace(/\s+/g, " ").slice(0, 500);
    const cause = error && error.message ? `: ${error.message}` : "";
    const suffix = preview ? `. Response starts with: ${preview}` : "";
    const failure = new Error(`Invalid JSON from ${route} (${status})${cause}${suffix}`);
    failure.name = "InvalidApiJsonError";
    failure.route = route;
    failure.status = response.status;
    return failure;
  }

  async function parseResponse(response, path) {
    const raw = await response.text();
    let data = {};
    if (raw.trim()) {
      try {
        data = JSON.parse(raw);
      } catch (error) {
        throw invalidJsonError(response, path, raw, error);
      }
    }
    if (!response.ok) {
      throw new Error(data.error || data.message || `HTTP ${response.status}`);
    }
    return data;
  }

  function timeoutValue(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }

  async function fetchWithTimeout(url, options, timeoutMs) {
    const timeout = timeoutValue(timeoutMs, 0);
    if (!timeout || typeof AbortController === "undefined") {
      return fetch(url, options);
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    try {
      return await fetch(url, { ...(options || {}), signal: controller.signal });
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error(`Request timed out after ${timeout} ms`);
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function apiGet(path, options = {}) {
    const timeoutMs = timeoutValue(options.timeoutMs, DEFAULT_GET_TIMEOUT_MS);
    const requestPath = normalizeApiPath(path);
    const response = await fetchWithTimeout(`${apiBase}${requestPath}`, {
      headers: apiHeaders(),
      cache: "no-store",
      credentials: "same-origin",
    }, timeoutMs);
    return parseResponse(response, requestPath);
  }

  async function apiPost(path, payload, options = {}) {
    const timeoutMs = timeoutValue(options.timeoutMs, 0);
    const requestPath = normalizeApiPath(path);
    const response = await fetchWithTimeout(`${apiBase}${requestPath}`, {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      cache: "no-store",
      credentials: "same-origin",
      body: JSON.stringify(payload || {}),
    }, timeoutMs);
    return parseResponse(response, requestPath);
  }

  /**
   * Public namespace for the API client module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineApi = {
    apiBase,
    tokenPresent: Boolean(token || bootstrap.tokenSource === "http-only-cookie"),
    apiGet,
    apiPost,
  };
  window.apiGet = apiGet;
  window.apiPost = apiPost;
})();
