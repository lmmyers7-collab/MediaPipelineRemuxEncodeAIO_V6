from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewApiClientSmokeTests(unittest.TestCase):
    def test_api_client_fails_closed_on_invalid_json_from_successful_api_routes(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the WebView API client smoke.")

        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");

            const sourcePath = path.join(process.cwd(), "apps/desktop/webview/static/assets/apiClient.js");
            const source = fs.readFileSync(sourcePath, "utf8");
            const fetchQueue = [];
            const fetchCalls = [];

            function enqueueResponse({ ok = true, status = 200, body = "", url = "", error = null, abortable = false }) {
              fetchQueue.push({
                ok,
                status,
                url,
                error,
                abortable,
                async text() {
                  return body;
                },
              });
            }

            const context = {
              console,
              URL,
              setTimeout,
              clearTimeout,
              AbortController,
              MEDIA_PIPELINE_BOOTSTRAP: {
                apiBase: "http://127.0.0.1:8765",
                token: "test-token",
                shellSurface: "webview",
              },
              MEDIA_PIPELINE_TAURI_BOOTSTRAP: Object.freeze({
                token: "test-token",
                tokenSource: "tauri-startup",
              }),
              async fetch(url, options = {}) {
                fetchCalls.push({ url: String(url), options });
                if (!fetchQueue.length) throw new Error("fetch called without an enqueued response");
                const response = fetchQueue.shift();
                if (response.error) throw response.error;
                if (response.abortable) {
                  return new Promise((_resolve, reject) => {
                    const signal = options && options.signal;
                    if (!signal || typeof signal.addEventListener !== "function") {
                      throw new Error("abortable response did not receive an AbortSignal");
                    }
                    signal.addEventListener("abort", () => {
                      const abortError = new Error("The operation was aborted");
                      abortError.name = "AbortError";
                      reject(abortError);
                    });
                  });
                }
                response.url = response.url || String(url);
                return response;
              },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: sourcePath });

            function requireNotIncludes(text, fragments) {
              for (const fragment of fragments) {
                if (String(text).includes(fragment)) {
                  throw new Error(`Expected text not to include ${fragment}; got ${text}`);
                }
              }
            }

            async function requireRejects(promise, fragments, properties = {}) {
              try {
                await promise;
              } catch (error) {
                const message = String(error && error.message || error);
                for (const fragment of fragments) {
                  if (!message.includes(fragment)) {
                    throw new Error(`Expected rejection to include ${fragment}; got ${message}`);
                  }
                }
                for (const [key, value] of Object.entries(properties)) {
                  if (error[key] !== value) {
                    throw new Error(`Expected rejection ${key} to be ${value}; got ${error[key]} from ${message}`);
                  }
                }
                return error;
              }
              throw new Error("Expected API client call to reject");
            }

            (async () => {
              const client = context.window.mediaPipelineApi;
              if (!client || typeof client.apiGet !== "function" || typeof client.apiPost !== "function") {
                throw new Error("API client globals were not exported");
              }
              if (!client.tokenPresent) throw new Error("API client did not report an available auth channel");
              if (Object.prototype.hasOwnProperty.call(context.MEDIA_PIPELINE_BOOTSTRAP, "token")) {
                throw new Error("MEDIA_PIPELINE_BOOTSTRAP retained the bearer token");
              }
              if (Object.prototype.hasOwnProperty.call(context.MEDIA_PIPELINE_TAURI_BOOTSTRAP, "token")) {
                throw new Error("MEDIA_PIPELINE_TAURI_BOOTSTRAP retained the bearer token");
              }
              if (context.MEDIA_PIPELINE_BOOTSTRAP.shellSurface !== "webview") {
                throw new Error("bootstrap token scrubber removed non-secret bootstrap fields");
              }
              if (client.apiBase !== "http://127.0.0.1:8765") {
                throw new Error(`API base was not normalized to the loopback origin: ${client.apiBase}`);
              }

              const fetchCallCountBeforeRejectedPaths = fetchCalls.length;
              await requireRejects(client.apiGet("https://example.invalid/api/health"), [
                "API path must be a local /api/ route",
              ]);
              await requireRejects(client.apiGet("//example.invalid/api/health"), [
                "API path must be a local /api/ route",
              ]);
              await requireRejects(client.apiPost("/assets/app.js", { unsafe: true }), [
                "API path must be a local /api/ route",
              ]);
              if (fetchCalls.length !== fetchCallCountBeforeRejectedPaths) {
                throw new Error("API client called fetch for a rejected route");
              }

              enqueueResponse({ ok: true, status: 200, body: "<html>not-json</html>" });
              const invalidGet = await requireRejects(client.apiGet("/api/health"), [
                "invalid JSON",
                "Couldn't load backend health",
                "/api/health",
                "HTTP 200",
                "unexpected error",
                "Try again; open Diagnostics if it continues.",
              ], { name: "InvalidApiJsonError", category: "unexpected error", status: 200 });
              requireNotIncludes(invalidGet.message, ["<html>", "not-json", "Response starts with"]);

              enqueueResponse({ ok: true, status: 200, body: "backend shutdown accepted" });
              await requireRejects(client.apiPost("/api/backend/shutdown", { reason: "test" }), [
                "invalid JSON",
                "Couldn't shut down backend",
                "/api/backend/shutdown",
                "HTTP 200",
                "unexpected error",
              ], { name: "InvalidApiJsonError", category: "unexpected error", status: 200 });

              enqueueResponse({ ok: true, status: 204, body: "" });
              const empty = await client.apiGet("/api/empty");
              if (!empty || Object.keys(empty).length !== 0) {
                throw new Error(`Expected empty successful response to parse as {}, got ${JSON.stringify(empty)}`);
              }

              enqueueResponse({ ok: false, status: 400, body: JSON.stringify({ error: { code: "PROJECT_NAME_MISSING", message: "project name is missing" } }) });
              await requireRejects(client.apiPost("/api/projects", {}, { action: "save project" }), [
                "Couldn't save project",
                "backend rejected POST /api/projects",
                "HTTP 400",
                "validation",
                "code PROJECT_NAME_MISSING",
                "project name is missing",
                "Check the request fields and try again.",
              ], { name: "ApiClientHttpError", category: "validation", code: "PROJECT_NAME_MISSING", status: 400 });

              enqueueResponse({ ok: false, status: 401, body: JSON.stringify({ error: "unauthorized" }) });
              await requireRejects(client.apiPost("/api/settings/save-patch", { changes: {} }), [
                "Session expired while saving settings",
                "HTTP 401",
                "authentication/session",
                "POST /api/settings/save-patch",
                "Sign in again.",
              ], { name: "ApiClientHttpError", category: "authentication/session", status: 401 });

              enqueueResponse({ ok: false, status: 403, body: JSON.stringify({ error: "permission denied" }) });
              await requireRejects(client.apiPost("/api/settings/save-patch", { changes: {} }), [
                "Couldn't save settings",
                "HTTP 403",
                "permission",
                "POST /api/settings/save-patch",
                "permission denied",
                "Check backend access, then try again.",
              ], { name: "ApiClientHttpError", category: "permission", status: 403 });

              enqueueResponse({ ok: false, status: 404, body: JSON.stringify({ error: "not found" }) });
              await requireRejects(client.apiGet("/api/jobs", { action: "load jobs" }), [
                "Couldn't load jobs",
                "HTTP 404",
                "not found",
                "GET /api/jobs",
                "Refresh the page and try again.",
              ], { name: "ApiClientHttpError", category: "not found", status: 404 });

              enqueueResponse({ ok: false, status: 409, body: JSON.stringify({ error: "it is still in use", code: "ACTIVE_WORK" }) });
              await requireRejects(client.apiPost("/api/backend/shutdown", { reason: "test" }), [
                "Couldn't shut down backend",
                "HTTP 409",
                "conflict",
                "code ACTIVE_WORK",
                "POST /api/backend/shutdown",
                "it is still in use",
                "Refresh and resolve the conflicting state before trying again.",
              ], { name: "ApiClientHttpError", category: "conflict", code: "ACTIVE_WORK", status: 409 });

              enqueueResponse({ ok: false, status: 429, body: JSON.stringify({ error: "too many requests" }) });
              await requireRejects(client.apiGet("/api/jobs", { action: "load jobs" }), [
                "Couldn't load jobs",
                "HTTP 429",
                "rate limit",
                "GET /api/jobs",
                "too many requests",
                "Wait a moment and try again.",
              ], { name: "ApiClientHttpError", category: "rate limit", status: 429 });

              enqueueResponse({ ok: false, status: 504, body: JSON.stringify({ error: "worker timed out after 30s" }) });
              await requireRejects(client.apiGet("/api/jobs", { action: "load jobs" }), [
                "Couldn't load jobs",
                "HTTP 504",
                "timeout",
                "GET /api/jobs",
                "worker timed out after 30s",
                "Try again.",
              ], { name: "ApiClientHttpError", category: "timeout", status: 504 });

              enqueueResponse({ ok: false, status: 500, body: JSON.stringify({ error: { code: "DB_WRITE_FAILED", message: "SELECT * FROM secrets WHERE token = 'abc' at C:\\\\Sensitive\\\\state.sqlite3" } }) });
              const storageFailure = await requireRejects(client.apiPost("/api/settings/save-patch", { changes: {} }), [
                "Couldn't save settings",
                "HTTP 500",
                "database/storage error",
                "code DB_WRITE_FAILED",
                "POST /api/settings/save-patch",
                "Open Diagnostics and check storage state before trying again.",
              ], { name: "ApiClientHttpError", category: "database/storage error", code: "DB_WRITE_FAILED", status: 500 });
              requireNotIncludes(storageFailure.message, ["SELECT", "token", "abc", "C:\\", "Sensitive", "state.sqlite3"]);

              enqueueResponse({ ok: false, status: 500, body: JSON.stringify({ error: "internal route error", error_id: "abc123def456" }) });
              await requireRejects(client.apiGet("/api/health"), [
                "Couldn't load backend health",
                "HTTP 500",
                "server error",
                "GET /api/health",
                "Try again; open Diagnostics if it continues.",
              ], { name: "ApiClientHttpError", category: "server error", status: 500 });

              enqueueResponse({ abortable: true });
              await requireRejects(client.apiGet("/api/jobs", { action: "load jobs", timeoutMs: 1 }), [
                "Couldn't load jobs",
                "backend timed out after 1ms",
                "GET /api/jobs",
                "timeout",
                "Try again.",
              ], { name: "ApiClientTimeoutError", category: "timeout", status: 0 });

              enqueueResponse({ error: new TypeError("Failed to fetch http://secret.internal:8765/path?token=abc") });
              const networkFailure = await requireRejects(client.apiGet("/api/jobs", { action: "load jobs" }), [
                "Couldn't connect to backend while loading jobs",
                "no response from GET /api/jobs",
                "network unavailable",
                "Check that the local backend is running, then try again.",
              ], { name: "ApiClientNetworkError", category: "network unavailable", status: 0 });
              requireNotIncludes(networkFailure.message, ["secret.internal", "token=abc", "Failed to fetch"]);

              const getCall = fetchCalls.find((call) => call.url.endsWith("/api/health"));
              if (!getCall) throw new Error("apiGet did not call fetch for /api/health");
              if (getCall.options.cache !== "no-store") throw new Error("apiGet must keep cache disabled");
              if (getCall.options.credentials !== "same-origin") throw new Error("apiGet must send same-origin auth cookies");
              if (getCall.options.headers.Authorization !== "Bearer test-token") {
                throw new Error("apiGet did not send the bootstrap bearer token");
              }

              const postCall = fetchCalls.find((call) => call.url.endsWith("/api/backend/shutdown"));
              if (!postCall) throw new Error("apiPost did not call fetch for /api/backend/shutdown");
              if (postCall.options.method !== "POST") throw new Error("apiPost did not use POST");
              if (postCall.options.headers["Content-Type"] !== "application/json") {
                throw new Error("apiPost did not send a JSON content type");
              }
            })().catch((error) => {
              console.error(error.stack || error.message || String(error));
              process.exit(1);
            });
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
