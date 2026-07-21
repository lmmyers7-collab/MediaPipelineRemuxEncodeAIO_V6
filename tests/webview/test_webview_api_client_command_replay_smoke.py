from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewApiClientCommandReplaySmokeTests(unittest.TestCase):
    def test_ambiguous_durable_posts_reuse_one_command_identity(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the WebView API client command-replay smoke.")

        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const path = require("path");
            const vm = require("vm");

            const sourcePath = path.join(process.cwd(), "apps/desktop/webview/static/assets/apiClient.js");
            const source = fs.readFileSync(sourcePath, "utf8");
            const commandHeader = "X-MediaPipeline-Command-ID";
            const durableRoutes = [
              "/api/pipeline/start",
              "/api/pipeline/control",
              "/api/audit/stop",
              "/api/backend/shutdown",
            ];
            const generatedIds = Array.from(
              { length: 32 },
              (_value, index) => `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
            );
            const steps = [];
            const calls = [];
            const failures = [];
            const serverResults = new Map();
            const mutationCounts = new Map();
            const timers = new Map();
            const barrierWaiters = [];
            let nextTimerId = 1;

            class DeterministicAbortSignal {
              constructor() {
                this.aborted = false;
                this.listeners = [];
              }

              addEventListener(name, callback) {
                if (name === "abort" && typeof callback === "function") this.listeners.push(callback);
              }

              dispatchAbort() {
                if (this.aborted) return;
                this.aborted = true;
                for (const callback of this.listeners.slice()) callback();
              }
            }

            class DeterministicAbortController {
              constructor() {
                this.signal = new DeterministicAbortSignal();
              }

              abort() {
                this.signal.dispatchAbort();
              }
            }

            function deterministicSetTimeout(callback) {
              const timerId = nextTimerId++;
              timers.set(timerId, callback);
              return timerId;
            }

            function deterministicClearTimeout(timerId) {
              timers.delete(timerId);
            }

            function fireOnlyTimer() {
              if (timers.size !== 1) {
                throw new Error(`Expected exactly one pending timeout callback; saw ${timers.size}`);
              }
              const [[timerId, callback]] = Array.from(timers.entries());
              timers.delete(timerId);
              callback();
            }

            function enqueue(label, kind, response = {}) {
              steps.push({ label, kind, ...response });
            }

            function responseFor(step, overrideBody = undefined) {
              const body = overrideBody === undefined ? (step.body || "") : overrideBody;
              return {
                ok: step.ok !== false,
                status: Number(step.status || (step.ok === false ? 500 : 200)),
                async text() {
                  return body;
                },
              };
            }

            function check(condition, message) {
              if (!condition) failures.push(message);
            }

            function commandIdFrom(options) {
              const headers = options && options.headers || {};
              return String(headers[commandHeader] || headers[commandHeader.toLowerCase()] || "");
            }

            function recordMutation(call) {
              const identity = call.commandId || `missing-command-id-${call.index}`;
              if (!serverResults.has(identity)) {
                serverResults.set(identity, JSON.stringify({ ok: true, replayed: false }));
                mutationCounts.set(call.label, Number(mutationCounts.get(call.label) || 0) + 1);
              }
              return serverResults.get(identity);
            }

            const context = {
              AbortController: DeterministicAbortController,
              URL,
              clearTimeout: deterministicClearTimeout,
              console,
              crypto: {
                randomUUID() {
                  if (!generatedIds.length) throw new Error("deterministic command-ID fixture exhausted");
                  return generatedIds.shift();
                },
              },
              MEDIA_PIPELINE_BOOTSTRAP: {
                apiBase: "http://127.0.0.1:8765",
                token: "test-token",
                durableCommandRoutes: durableRoutes,
              },
              setTimeout: deterministicSetTimeout,
              async fetch(url, options = {}) {
                if (!steps.length) throw new Error(`Unexpected fetch for ${url}`);
                const step = steps.shift();
                const call = {
                  body: JSON.parse(String(options.body || "{}")),
                  commandId: commandIdFrom(options),
                  index: calls.length,
                  label: step.label,
                  method: String(options.method || "GET"),
                  url: String(url),
                };
                calls.push(call);

                if (step.kind === "barrier") {
                  return new Promise((resolve) => {
                    barrierWaiters.push({ resolve, step });
                    if (barrierWaiters.length === 2) {
                      const waiting = barrierWaiters.splice(0, barrierWaiters.length);
                      for (const waiter of waiting) waiter.resolve(responseFor(waiter.step));
                    }
                  });
                }
                if (step.kind === "network-after-mutation") {
                  recordMutation(call);
                  throw new TypeError("injected transport loss after server mutation");
                }
                if (step.kind === "replay") {
                  const result = recordMutation(call);
                  return responseFor(step, result);
                }
                if (step.kind === "timeout-after-mutation") {
                  recordMutation(call);
                  return new Promise((_resolve, reject) => {
                    const signal = options && options.signal;
                    if (!signal || typeof signal.addEventListener !== "function") {
                      throw new Error("timeout fixture did not receive an AbortSignal");
                    }
                    signal.addEventListener("abort", () => {
                      const error = new Error("deterministic abort");
                      error.name = "AbortError";
                      reject(error);
                    });
                    fireOnlyTimer();
                  });
                }
                if (step.kind === "invalid-json") {
                  recordMutation(call);
                  return responseFor(step, "<html>lost JSON response</html>");
                }
                return responseFor(step);
              },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: sourcePath });

            async function captureRejection(promise, label) {
              try {
                await promise;
              } catch (error) {
                return error;
              }
              failures.push(`${label}: expected rejection`);
              return new Error(`${label}: missing rejection`);
            }

            function assertAmbiguous(error, commandId, label) {
              const message = String(error && error.message || error);
              check(error && error.ambiguousOutcome === true, `${label}: error did not mark ambiguousOutcome=true`);
              check(error && error.commandId === commandId, `${label}: error did not retain exact commandId`);
              check(message.includes("Outcome is unknown"), `${label}: message did not label the outcome unknown: ${message}`);
              check(message.includes("Do not submit a new command"), `${label}: message encouraged an unsafe second command: ${message}`);
              check(message.includes(commandId), `${label}: message omitted the reusable command ID: ${message}`);
              check(!/\bTry again\b/.test(message), `${label}: message retained generic retry advice: ${message}`);
            }

            function callsFor(label) {
              return calls.filter((call) => call.label === label);
            }

            (async () => {
              const client = context.window.mediaPipelineApi;
              check(client && typeof client.apiPost === "function", "API client apiPost export is unavailable");

              const simultaneousA = Object.freeze({ mode: "once", show_console: true });
              const simultaneousB = Object.freeze({ show_console: true, mode: "once" });
              enqueue("simultaneous", "barrier", { body: JSON.stringify({ ok: true, request: "a" }) });
              enqueue("simultaneous", "barrier", { body: JSON.stringify({ ok: true, request: "b" }) });
              await Promise.all([
                client.apiPost("/api/pipeline/start", simultaneousA),
                client.apiPost("/api/pipeline/start", simultaneousB),
              ]);
              const simultaneousCalls = callsFor("simultaneous");
              check(simultaneousCalls.length === 2, `simultaneous: expected two requests, saw ${simultaneousCalls.length}`);
              check(Boolean(simultaneousCalls[0]?.commandId), "simultaneous: first request omitted command ID header");
              check(
                simultaneousCalls[0]?.commandId === simultaneousCalls[1]?.commandId,
                `simultaneous: equivalent payloads used different IDs: ${JSON.stringify(simultaneousCalls)}`,
              );
              check(
                JSON.stringify(simultaneousCalls[0]?.body) === JSON.stringify({ mode: "once", show_console: true }),
                `simultaneous: command metadata changed the first wire body: ${JSON.stringify(simultaneousCalls[0]?.body)}`,
              );
              check(
                JSON.stringify(simultaneousCalls[1]?.body) === JSON.stringify({ show_console: true, mode: "once" }),
                `simultaneous: command metadata changed the second wire body: ${JSON.stringify(simultaneousCalls[1]?.body)}`,
              );
              check(!Object.prototype.hasOwnProperty.call(simultaneousA, "command_id"), "simultaneous: caller payload was mutated");

              enqueue("new-intent-after-success", "response", { body: JSON.stringify({ ok: true }) });
              await client.apiPost("/api/pipeline/start", { mode: "once", show_console: true });
              const newIntent = callsFor("new-intent-after-success")[0];
              check(Boolean(newIntent?.commandId), "new intent: request omitted command ID header");
              check(
                newIntent?.commandId !== simultaneousCalls[0]?.commandId,
                "new intent: completed command identity was retained after a definitive success",
              );

              const lostPayload = Object.freeze({ reason: "lost-response" });
              enqueue("lost-response", "network-after-mutation");
              const lostError = await captureRejection(
                client.apiPost("/api/backend/shutdown", lostPayload),
                "lost response",
              );
              const lostFirst = callsFor("lost-response")[0];
              assertAmbiguous(lostError, lostFirst?.commandId, "lost response");
              enqueue("lost-response-retry", "replay");
              await client.apiPost("/api/backend/shutdown", { reason: "lost-response" });
              const lostRetry = callsFor("lost-response-retry")[0];
              check(
                lostFirst?.commandId === lostRetry?.commandId && Boolean(lostRetry?.commandId),
                `lost response: retry did not reuse identity: ${lostFirst?.commandId} / ${lostRetry?.commandId}`,
              );
              check(
                Number(mutationCounts.get("lost-response") || 0) + Number(mutationCounts.get("lost-response-retry") || 0) === 1,
                "lost response: fake server observed more than one mutation",
              );

              const timeoutPayload = { action: "stop", expected_run_id: "run-timeout" };
              enqueue("timeout", "timeout-after-mutation");
              const timeoutError = await captureRejection(
                client.apiPost("/api/pipeline/control", timeoutPayload, { timeoutMs: 2500 }),
                "timeout",
              );
              const timeoutFirst = callsFor("timeout")[0];
              assertAmbiguous(timeoutError, timeoutFirst?.commandId, "timeout");
              enqueue("timeout-retry", "replay");
              await client.apiPost("/api/pipeline/control", { expected_run_id: "run-timeout", action: "stop" });
              const timeoutRetry = callsFor("timeout-retry")[0];
              check(
                timeoutFirst?.commandId === timeoutRetry?.commandId && Boolean(timeoutRetry?.commandId),
                `timeout: retry did not reuse identity: ${timeoutFirst?.commandId} / ${timeoutRetry?.commandId}`,
              );

              const invalidPayload = { confirm_stop: true, reason: "invalid-json" };
              enqueue("invalid-json", "invalid-json", { status: 200 });
              const invalidError = await captureRejection(
                client.apiPost("/api/audit/stop", invalidPayload),
                "invalid JSON",
              );
              const invalidFirst = callsFor("invalid-json")[0];
              assertAmbiguous(invalidError, invalidFirst?.commandId, "invalid JSON");
              enqueue("invalid-json-retry", "replay");
              await client.apiPost("/api/audit/stop", { reason: "invalid-json", confirm_stop: true });
              const invalidRetry = callsFor("invalid-json-retry")[0];
              check(
                invalidFirst?.commandId === invalidRetry?.commandId && Boolean(invalidRetry?.commandId),
                `invalid JSON: retry did not reuse identity: ${invalidFirst?.commandId} / ${invalidRetry?.commandId}`,
              );

              const unknownPayload = { reason: "terminal-journal-unknown" };
              enqueue("server-unknown", "response", {
                ok: false,
                status: 503,
                body: JSON.stringify({
                  error: {
                    code: "COMMAND_OUTCOME_UNKNOWN",
                    message: "The command may have run; inspect evidence before retrying.",
                  },
                }),
              });
              const unknownError = await captureRejection(
                client.apiPost("/api/backend/shutdown", unknownPayload),
                "server unknown",
              );
              const unknownFirst = callsFor("server-unknown")[0];
              assertAmbiguous(unknownError, unknownFirst?.commandId, "server unknown");
              enqueue("server-unknown-retry", "response", { body: JSON.stringify({ ok: true, replayed: true }) });
              await client.apiPost("/api/backend/shutdown", { reason: "terminal-journal-unknown" });
              const unknownRetry = callsFor("server-unknown-retry")[0];
              check(
                unknownFirst?.commandId === unknownRetry?.commandId && Boolean(unknownRetry?.commandId),
                `server unknown: retry did not reuse identity: ${unknownFirst?.commandId} / ${unknownRetry?.commandId}`,
              );

              const rejectedPayload = { confirm_stop: false, reason: "strict-confirmation-rejected" };
              enqueue("strict-rejection", "response", {
                ok: false,
                status: 400,
                body: JSON.stringify({
                  error: { code: "STRICT_CONFIRMATION_REQUIRED", message: "confirm_stop must be true" },
                }),
              });
              const rejectedError = await captureRejection(
                client.apiPost("/api/audit/stop", rejectedPayload),
                "strict rejection",
              );
              const rejectedFirst = callsFor("strict-rejection")[0];
              check(rejectedError?.ambiguousOutcome !== true, "strict rejection: definitive validation failure was marked ambiguous");
              enqueue("strict-rejection-resubmit", "response", { body: JSON.stringify({ ok: true }) });
              await client.apiPost("/api/audit/stop", { reason: "strict-confirmation-rejected", confirm_stop: false });
              const rejectedAgain = callsFor("strict-rejection-resubmit")[0];
              check(Boolean(rejectedFirst?.commandId), "strict rejection: request omitted command ID header");
              check(
                rejectedFirst?.commandId !== rejectedAgain?.commandId && Boolean(rejectedAgain?.commandId),
                "strict rejection: definitive rejection retained/reserved the previous client command ID",
              );

              check(steps.length === 0, `unused fake fetch steps remain: ${JSON.stringify(steps)}`);
              check(timers.size === 0, `deterministic timeout callbacks leaked: ${timers.size}`);
              if (failures.length) throw new Error(`API client command-replay failures:\n- ${failures.join("\n- ")}`);
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


if __name__ == "__main__":
    unittest.main()
