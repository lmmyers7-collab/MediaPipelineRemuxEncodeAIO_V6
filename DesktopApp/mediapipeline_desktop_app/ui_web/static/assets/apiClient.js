(function () {
  const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};
  const apiBase = bootstrap.apiBase || "";
  const token = bootstrap.token || "";
  const DEFAULT_GET_TIMEOUT_MS = 30000;

  function apiHeaders(extraHeaders) {
    const headers = { ...(extraHeaders || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async function parseResponse(response) {
    const raw = await response.text();
    let data = {};
    if (raw.trim()) {
      try {
        data = JSON.parse(raw);
      } catch (error) {
        data = { error: raw.slice(0, 500) };
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
    const response = await fetchWithTimeout(`${apiBase}${path}`, {
      headers: apiHeaders(),
      cache: "no-store",
    }, timeoutMs);
    return parseResponse(response);
  }

  async function apiPost(path, payload, options = {}) {
    const timeoutMs = timeoutValue(options.timeoutMs, 0);
    const response = await fetchWithTimeout(`${apiBase}${path}`, {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      cache: "no-store",
      body: JSON.stringify(payload || {}),
    }, timeoutMs);
    return parseResponse(response);
  }

  /**
   * Public namespace for the API client module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineApi = {
    apiBase,
    tokenPresent: Boolean(token),
    apiGet,
    apiPost,
  };
  window.apiGet = apiGet;
  window.apiPost = apiPost;
})();
