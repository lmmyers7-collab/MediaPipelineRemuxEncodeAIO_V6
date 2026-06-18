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

            function enqueueResponse({ ok = true, status = 200, body = "", url = "" }) {
              fetchQueue.push({
                ok,
                status,
                url,
                async text() {
                  return body;
                },
              });
            }

            const context = {
              console,
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
                response.url = response.url || String(url);
                return response;
              },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: sourcePath });

            async function requireRejects(promise, fragments) {
              try {
                await promise;
              } catch (error) {
                const message = String(error && error.message || error);
                for (const fragment of fragments) {
                  if (!message.includes(fragment)) {
                    throw new Error(`Expected rejection to include ${fragment}; got ${message}`);
                  }
                }
                return message;
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

              enqueueResponse({ ok: true, status: 200, body: "<html>not-json</html>" });
              await requireRejects(client.apiGet("/api/health"), [
                "Invalid JSON",
                "/api/health",
                "HTTP 200",
              ]);

              enqueueResponse({ ok: true, status: 200, body: "backend shutdown accepted" });
              await requireRejects(client.apiPost("/api/backend/shutdown", { reason: "test" }), [
                "Invalid JSON",
                "/api/backend/shutdown",
                "HTTP 200",
              ]);

              enqueueResponse({ ok: true, status: 204, body: "" });
              const empty = await client.apiGet("/api/empty");
              if (!empty || Object.keys(empty).length !== 0) {
                throw new Error(`Expected empty successful response to parse as {}, got ${JSON.stringify(empty)}`);
              }

              enqueueResponse({ ok: false, status: 409, body: JSON.stringify({ error: "not safe to close" }) });
              await requireRejects(client.apiPost("/api/backend/shutdown", { reason: "test" }), [
                "not safe to close",
              ]);

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
