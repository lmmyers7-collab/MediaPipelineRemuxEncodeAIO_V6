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
  const GENERIC_BACKEND_DETAILS = new Set([
    "internal route error",
    "not found",
    "unauthorized",
  ]);
  const ROUTE_ACTIONS = [
    { method: "GET", pattern: /^\/api\/health$/, action: "load backend health" },
    { method: "GET", pattern: /^\/api\/snapshot$/, action: "load backend snapshot" },
    { method: "GET", pattern: /^\/api\/backend\/close-readiness$/, action: "load backend close-readiness" },
    { method: "GET", pattern: /^\/api\/queue(?:\/|$)/, action: "load queue" },
    { method: "GET", pattern: /^\/api\/completed(?:\/|$)/, action: "load completed jobs" },
    { method: "GET", pattern: /^\/api\/pending-publish(?:\/|$)/, action: "load pending publish" },
    { method: "GET", pattern: /^\/api\/settings(?:\/|$)/, action: "load settings" },
    { method: "GET", pattern: /^\/api\/diagnostics(?:\/|$)/, action: "load diagnostics" },
    { method: "GET", pattern: /^\/api\/network(?:\/|$)/, action: "load network state" },
    { method: "POST", pattern: /^\/api\/backend\/shutdown$/, action: "shut down backend" },
    { method: "POST", pattern: /^\/api\/settings\/save-patch$/, action: "save settings" },
    { method: "POST", pattern: /^\/api\/settings\/preview-patch$/, action: "preview settings" },
    { method: "POST", pattern: /^\/api\/settings\/validate$/, action: "validate settings" },
    { method: "POST", pattern: /^\/api\/settings\/reload$/, action: "reload settings" },
    { method: "POST", pattern: /^\/api\/settings\/browse-path$/, action: "browse settings path" },
    { method: "POST", pattern: /^\/api\/queue\/source-scan$/, action: "scan queue sources" },
    { method: "POST", pattern: /^\/api\/queue\/priority(?:\/|$)/, action: "update queue priority" },
    { method: "POST", pattern: /^\/api\/queue\/strategy$/, action: "save queue strategy" },
    { method: "POST", pattern: /^\/api\/queue\/file-overrides(?:\/|$)/, action: "save queue file overrides" },
    { method: "POST", pattern: /^\/api\/completed\/open$/, action: "open completed item" },
    { method: "POST", pattern: /^\/api\/completed\/repair-sidecar-metadata/, action: "repair completed sidecar metadata" },
    { method: "POST", pattern: /^\/api\/completed\/reconcile-manifest/, action: "reconcile completed manifest" },
    { method: "POST", pattern: /^\/api\/pending-publish\/drain/, action: "drain pending publish" },
    { method: "POST", pattern: /^\/api\/pending-publish\/repair/, action: "repair pending publish" },
    { method: "POST", pattern: /^\/api\/sample-validation\/preview$/, action: "preview sample validation record" },
    { method: "POST", pattern: /^\/api\/sample-validation\/append$/, action: "append sample validation record" },
    { method: "POST", pattern: /^\/api\/diagnostics\/open$/, action: "open diagnostics item" },
    { method: "POST", pattern: /^\/api\/diagnostics\/tdarr-matrix/, action: "run Tdarr Matrix diagnostics" },
    { method: "POST", pattern: /^\/api\/final-library-promotion\/promote-queue$/, action: "start final library promotion" },
    { method: "POST", pattern: /^\/api\/final-library-promotion\/pause$/, action: "pause final library promotion" },
    { method: "POST", pattern: /^\/api\/final-library-promotion\/resume$/, action: "resume final library promotion" },
    { method: "POST", pattern: /^\/api\/pipeline\/control$/, action: "send pipeline control" },
    { method: "POST", pattern: /^\/api\/pipeline\/start$/, action: "start pipeline" },
    { method: "POST", pattern: /^\/api\/rerun/, action: "start rerun" },
    { method: "POST", pattern: /^\/api\/rename\/preview/, action: "preview rename" },
    { method: "POST", pattern: /^\/api\/rename\/apply/, action: "apply rename" },
    { method: "POST", pattern: /^\/api\/rename\/undo/, action: "undo rename" },
    { method: "POST", pattern: /^\/api\/failures\/artifacts\/cleanup$/, action: "clean up failure artifacts" },
    { method: "POST", pattern: /^\/api\/failures(?:\/|$)/, action: "update failure evidence" },
    { method: "POST", pattern: /^\/api\/audit\/start$/, action: "start audit" },
    { method: "POST", pattern: /^\/api\/audit\/stop$/, action: "stop audit" },
    { method: "POST", pattern: /^\/api\/audit(?:\/|$)/, action: "update audit" },
    { method: "POST", pattern: /^\/api\/ui-preferences$/, action: "save UI preferences" },
  ];
  const GERUND_BY_VERB = {
    append: "appending",
    apply: "applying",
    archive: "archiving",
    browse: "browsing",
    clean: "cleaning",
    cleanup: "cleaning up",
    clear: "clearing",
    connect: "connecting",
    delete: "deleting",
    drain: "draining",
    export: "exporting",
    import: "importing",
    load: "loading",
    open: "opening",
    pause: "pausing",
    preview: "previewing",
    read: "reading",
    reconcile: "reconciling",
    reload: "reloading",
    remove: "removing",
    repair: "repairing",
    resume: "resuming",
    run: "running",
    save: "saving",
    scan: "scanning",
    send: "sending",
    shut: "shutting",
    start: "starting",
    stop: "stopping",
    undo: "undoing",
    update: "updating",
    validate: "validating",
  };

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

  function routeOnly(path) {
    const value = String(path || "").trim();
    const marker = value.search(/[?#]/);
    return marker >= 0 ? value.slice(0, marker) : value;
  }

  function endpointLabel(method, path) {
    return `${String(method || "GET").toUpperCase()} ${routeOnly(path) || "/api"}`;
  }

  function humanizeSegment(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function gerundForAction(action) {
    const words = humanizeSegment(action).split(" ").filter(Boolean);
    if (!words.length) return "calling backend";
    const first = words[0].toLowerCase();
    const gerund = GERUND_BY_VERB[first] || `${first}ing`;
    return [gerund, ...words.slice(1)].join(" ");
  }

  function actionDescriptor(action) {
    const verb = humanizeSegment(action);
    return {
      verb: verb || "call backend",
      gerund: gerundForAction(verb || "call backend"),
    };
  }

  function routeResourceLabel(route) {
    const parts = String(route || "")
      .replace(/^\/api\/?/, "")
      .split("/")
      .map(humanizeSegment)
      .filter(Boolean);
    if (!parts.length) return "backend";
    if (parts[0] === "final library promotion") return "final library promotion";
    if (parts[0] === "pending publish") return "pending publish";
    if (parts[0] === "backend" && parts[1]) return `backend ${parts[1]}`;
    return parts.slice(0, 2).join(" ");
  }

  function genericPostAction(route) {
    const parts = String(route || "")
      .replace(/^\/api\/?/, "")
      .split("/")
      .map(humanizeSegment)
      .filter(Boolean);
    const domain = parts[0] || "backend";
    const operation = parts[parts.length - 1] || "request";
    const firstWord = operation.split(" ")[0].toLowerCase();
    if (Object.prototype.hasOwnProperty.call(GERUND_BY_VERB, firstWord)) {
      return `${firstWord} ${domain}`;
    }
    return `run ${domain} request`;
  }

  function requestAction(method, path, options = {}) {
    if (options && typeof options.action === "string" && options.action.trim()) {
      return actionDescriptor(options.action);
    }
    const normalizedMethod = String(method || "GET").toUpperCase();
    const route = routeOnly(path);
    const match = ROUTE_ACTIONS.find((item) => (
      item.method === normalizedMethod && item.pattern.test(route)
    ));
    if (match) return actionDescriptor(match.action);
    if (normalizedMethod === "GET") return actionDescriptor(`load ${routeResourceLabel(route)}`);
    if (normalizedMethod === "POST") return actionDescriptor(genericPostAction(route));
    return actionDescriptor(`call ${routeResourceLabel(route)}`);
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

  function boundedText(value, limit = 180) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > limit ? `${text.slice(0, Math.max(0, limit - 3))}...` : text;
  }

  function looksLikeStackTrace(text) {
    return /Traceback\s*\(|Traceback \(most recent call last\)|\bFile\s+"[^"]+",\s+line\s+\d+|\bat\s+\S+\s+\(|Stack trace/i.test(text);
  }

  function looksLikeRawSql(text) {
    return /\b(select|insert|update|delete|drop|alter|create)\b[\s\S]{0,120}\b(from|into|where|table|values|set)\b/i.test(text);
  }

  function looksLikeSensitivePayload(text) {
    return /"[^"]+"\s*:/.test(text) || (text.includes("{") && text.includes("}"));
  }

  function redactSensitiveText(value) {
    let text = String(value || "");
    text = text.replace(/\bBearer\s+[A-Za-z0-9._~+/-]+=*/gi, "Bearer [redacted]");
    text = text.replace(/\b(token|password|secret|authorization|credential|api[_-]?key)\s*[:=]\s*["']?[^,;\s"']+/gi, "$1=[redacted]");
    text = text.replace(/[A-Za-z]:\\(?:[^\s\\/:*?"<>|]+\\?)+/g, "[local path]");
    text = text.replace(/\\\\[^\s\\\/]+\\[^\s]+/g, "[network path]");
    text = text.replace(/https?:\/\/(?!127\.0\.0\.1(?::|\/|$)|localhost(?::|\/|$)|\[::1\](?::|\/|$))[^\s)]+/gi, "[backend URL]");
    text = text.replace(/\b[A-Za-z0-9-]+(?:\.(?:local|lan|internal|corp|home))+(:\d+)?\b/gi, "[internal host]");
    return text;
  }

  function sanitizeBackendDetail(value) {
    if (value === undefined || value === null) return "";
    let text = String(value).split(/\r?\n/)[0] || "";
    if (!text.trim()) return "";
    if (looksLikeStackTrace(text) || looksLikeRawSql(text) || looksLikeSensitivePayload(text)) return "";
    text = redactSensitiveText(text);
    text = boundedText(text.replace(/[.。]+$/u, ""), 180);
    if (!text || GENERIC_BACKEND_DETAILS.has(text.toLowerCase())) return "";
    return text;
  }

  function backendEnvelopeObject(data) {
    if (!data || typeof data !== "object") return {};
    const nestedError = data.error && typeof data.error === "object" ? data.error : {};
    return { ...data, ...nestedError };
  }

  function backendErrorCode(data) {
    const envelope = backendEnvelopeObject(data);
    const raw = envelope.code || envelope.error_code || envelope.errorCode || "";
    const code = String(raw || "").trim();
    if (!code || /token|password|secret|authorization|credential/i.test(code)) return "";
    if (!/^[A-Za-z0-9_.:-]{1,80}$/.test(code)) return "";
    return code;
  }

  function backendDetail(data) {
    if (!data || typeof data !== "object") return "";
    const envelope = backendEnvelopeObject(data);
    const candidates = [
      envelope.message,
      envelope.detail,
      envelope.reason,
      typeof data.error === "string" ? data.error : "",
    ];
    for (const candidate of candidates) {
      const safe = sanitizeBackendDetail(candidate);
      if (safe) return safe;
    }
    return "";
  }

  function categoryForStatus(status, code, detail) {
    const numericStatus = Number(status);
    const probe = `${code || ""} ${detail || ""}`.toLowerCase();
    if (numericStatus === 401) return "authentication/session";
    if (numericStatus === 403) return "permission";
    if (numericStatus === 404) return "not found";
    if (numericStatus === 408 || numericStatus === 504) return "timeout";
    if (numericStatus === 409 || numericStatus === 423) return "conflict";
    if (numericStatus === 413 || numericStatus === 415 || numericStatus === 422 || numericStatus === 400) return "validation";
    if (numericStatus === 429) return "rate limit";
    if (numericStatus === 507 || /db|database|sqlite|sql|storage|disk|state store|no space|i\/o|io error/.test(probe)) {
      return "database/storage error";
    }
    if (numericStatus >= 500) return "server error";
    return "unexpected error";
  }

  function nextStepForCategory(category) {
    switch (category) {
      case "validation":
        return "Check the request fields and try again.";
      case "authentication/session":
        return "Sign in again.";
      case "permission":
        return "Check backend access, then try again.";
      case "not found":
        return "Refresh the page and try again.";
      case "conflict":
        return "Refresh and resolve the conflicting state before trying again.";
      case "rate limit":
        return "Wait a moment and try again.";
      case "timeout":
        return "Try again.";
      case "network unavailable":
        return "Check that the local backend is running, then try again.";
      case "database/storage error":
        return "Open Diagnostics and check storage state before trying again.";
      case "server error":
        return "Try again; open Diagnostics if it continues.";
      default:
        return "Try again; open Diagnostics if it continues.";
    }
  }

  function categoryCodeText(category, code) {
    return code ? `${category}; code ${code}` : category;
  }

  function apiClientError(name, message, metadata = {}) {
    const failure = new Error(message);
    failure.name = name || "ApiClientError";
    Object.assign(failure, metadata);
    return failure;
  }

  function invalidJsonError(response, path, raw, error, method, options = {}) {
    const action = requestAction(method, path, options);
    const endpoint = endpointLabel(method, path);
    const status = Number(response.status);
    const statusText = Number.isFinite(status) ? `HTTP ${status}` : "HTTP response";
    const message = `Couldn't ${action.verb}: backend returned invalid JSON from ${endpoint} (${statusText}, unexpected error). ${nextStepForCategory("unexpected error")}`;
    return apiClientError("InvalidApiJsonError", message, {
      action: action.verb,
      category: "unexpected error",
      endpoint,
      route: routeOnly(path),
      status: response.status,
      parseError: error && error.message ? boundedText(error.message, 200) : "",
    });
  }

  function httpError(response, path, data, method, options = {}) {
    const action = requestAction(method, path, options);
    const endpoint = endpointLabel(method, path);
    const status = Number(response.status);
    const code = backendErrorCode(data);
    const detail = backendDetail(data);
    const category = categoryForStatus(status, code, detail);
    const nextStep = nextStepForCategory(category);
    if (category === "authentication/session") {
      return apiClientError(
        "ApiClientHttpError",
        `Session expired while ${action.gerund} (HTTP ${response.status}, authentication/session from ${endpoint}). ${nextStep}`,
        { action: action.verb, category, code, endpoint, route: routeOnly(path), status: response.status }
      );
    }
    const codeText = categoryCodeText(category, code);
    const detailText = detail ? ` because ${detail}` : "";
    let message;
    if (category === "validation") {
      message = `Couldn't ${action.verb}: backend rejected ${endpoint} with HTTP ${response.status} (${codeText})${detailText}. ${nextStep}`;
    } else {
      message = `Couldn't ${action.verb}: backend returned HTTP ${response.status} (${codeText}) from ${endpoint}${detailText}. ${nextStep}`;
    }
    return apiClientError("ApiClientHttpError", message, {
      action: action.verb,
      category,
      code,
      detail,
      endpoint,
      route: routeOnly(path),
      status: response.status,
    });
  }

  async function parseResponse(response, path, method, options = {}) {
    const raw = await response.text();
    let data = {};
    if (raw.trim()) {
      try {
        data = JSON.parse(raw);
      } catch (error) {
        throw invalidJsonError(response, path, raw, error, method, options);
      }
    }
    if (!response.ok) {
      throw httpError(response, path, data, method, options);
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
        throw apiClientError("ApiClientTimeoutError", "request timed out", { timeoutMs: timeout });
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function durationText(ms) {
    const numeric = Number(ms);
    if (!Number.isFinite(numeric) || numeric <= 0) return "the request timeout";
    if (numeric % 1000 === 0) return `${numeric / 1000}s`;
    return `${numeric}ms`;
  }

  function requestFailure(error, method, path, options, timeoutMs) {
    if (error && (error.name === "ApiClientHttpError" || error.name === "InvalidApiJsonError")) {
      return error;
    }
    const action = requestAction(method, path, options);
    const endpoint = endpointLabel(method, path);
    if (error && error.name === "ApiClientTimeoutError") {
      return apiClientError(
        "ApiClientTimeoutError",
        `Couldn't ${action.verb}: backend timed out after ${durationText(error.timeoutMs || timeoutMs)} for ${endpoint} (timeout). ${nextStepForCategory("timeout")}`,
        {
          action: action.verb,
          category: "timeout",
          endpoint,
          route: routeOnly(path),
          status: 0,
          timeoutMs: error.timeoutMs || timeoutMs,
        }
      );
    }
    return apiClientError(
      "ApiClientNetworkError",
      `Couldn't connect to backend while ${action.gerund}: no response from ${endpoint} (network unavailable). ${nextStepForCategory("network unavailable")}`,
      {
        action: action.verb,
        category: "network unavailable",
        endpoint,
        route: routeOnly(path),
        status: 0,
      }
    );
  }

  async function apiRequest(method, path, payload, options = {}) {
    const requestPath = normalizeApiPath(path);
    const normalizedMethod = String(method || "GET").toUpperCase();
    const timeoutMs = timeoutValue(
      options.timeoutMs,
      normalizedMethod === "GET" ? DEFAULT_GET_TIMEOUT_MS : 0
    );
    const requestOptions = {
      method: normalizedMethod === "GET" ? undefined : normalizedMethod,
      headers: normalizedMethod === "GET"
        ? apiHeaders()
        : apiHeaders({ "Content-Type": "application/json" }),
      cache: "no-store",
      credentials: "same-origin",
    };
    if (normalizedMethod !== "GET") requestOptions.body = JSON.stringify(payload || {});
    try {
      const response = await fetchWithTimeout(`${apiBase}${requestPath}`, requestOptions, timeoutMs);
      return await parseResponse(response, requestPath, normalizedMethod, options);
    } catch (error) {
      throw requestFailure(error, normalizedMethod, requestPath, options, timeoutMs);
    }
  }

  async function apiGet(path, options = {}) {
    return apiRequest("GET", path, null, options);
  }

  async function apiPost(path, payload, options = {}) {
    return apiRequest("POST", path, payload, options);
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
