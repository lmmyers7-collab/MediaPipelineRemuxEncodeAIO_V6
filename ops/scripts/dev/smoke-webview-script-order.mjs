import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";
import {
  collectScriptTags,
  repoRoot,
  scriptSrcToRepoPath,
} from "./webview-tooling-common.mjs";

function noop() {}

function classList() {
  const values = new Set();
  return {
    add: (...items) => items.forEach((item) => values.add(item)),
    remove: (...items) => items.forEach((item) => values.delete(item)),
    contains: (item) => values.has(item),
    toggle: (item, force) => {
      if (force === true) {
        values.add(item);
        return true;
      }
      if (force === false) {
        values.delete(item);
        return false;
      }
      if (values.has(item)) {
        values.delete(item);
        return false;
      }
      values.add(item);
      return true;
    },
  };
}

function fakeElement(tagName = "div") {
  const element = {
    tagName: tagName.toUpperCase(),
    style: {},
    dataset: {},
    children: [],
    classList: classList(),
    setAttribute: noop,
    removeAttribute: noop,
    getAttribute: () => null,
    hasAttribute: () => false,
    append: (...items) => element.children.push(...items),
    appendChild: (item) => {
      element.children.push(item);
      return item;
    },
    replaceChildren: (...items) => {
      element.children = [...items];
    },
    addEventListener: noop,
    removeEventListener: noop,
    querySelector: () => null,
    querySelectorAll: () => [],
    closest: () => null,
    matches: () => false,
    getClientRects: () => [],
    cells: [],
    textContent: "",
    innerHTML: "",
    value: "",
    checked: false,
    disabled: false,
  };
  return element;
}

function createContext() {
  const body = fakeElement("body");
  const listeners = [];
  const context = {
    console,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    AbortController,
    URL,
    URLSearchParams,
    TextEncoder,
    TextDecoder,
    CustomEvent: class CustomEvent {
      constructor(type, options = {}) {
        this.type = type;
        this.detail = options.detail;
      }
    },
    Event: class Event {
      constructor(type, options = {}) {
        this.type = type;
        this.defaultPrevented = false;
        this.cancelable = options.cancelable !== false;
      }
      preventDefault() {
        this.defaultPrevented = true;
      }
    },
    navigator: { userAgent: "webview-script-order-smoke" },
    location: { href: "http://localhost/", origin: "http://localhost" },
    localStorage: {
      getItem: () => null,
      setItem: noop,
      removeItem: noop,
    },
    sessionStorage: {
      getItem: () => null,
      setItem: noop,
      removeItem: noop,
    },
    document: {
      readyState: "loading",
      body,
      documentElement: fakeElement("html"),
      scrollingElement: fakeElement("html"),
      addEventListener: (type, callback) => listeners.push({ target: "document", type, callback }),
      removeEventListener: noop,
      querySelector: () => null,
      querySelectorAll: () => [],
      getElementById: () => null,
      createElement: fakeElement,
      createTextNode: (text) => ({ textContent: String(text) }),
    },
    fetch: async () => ({
      ok: false,
      status: 599,
      json: async () => ({}),
      text: async () => "",
    }),
  };
  context.window = context;
  context.globalThis = context;
  context.self = context;
  context.window.addEventListener = (type, callback) => listeners.push({ target: "window", type, callback });
  context.window.removeEventListener = noop;
  context.window.dispatchEvent = noop;
  context.window.scrollTo = noop;
  context.__registeredListeners = listeners;
  return vm.createContext(context);
}

const requiredGlobals = [
  "apiGet",
  "apiPost",
  "appendCells",
  "byId",
  "mediaPipelineApi",
  "mediaPipelineCompletedView",
  "mediaPipelineDom",
  "mediaPipelineLaunchView",
  "mediaPipelineNetworkView",
  "mediaPipelineQueueView",
  "mediaPipelineSettingsMetadata",
  "mediaPipelineSettingsOverview",
  "mediaPipelineSettingsView",
  "refreshAll",
  "refreshAllNow",
  "setText",
  "showPage",
];

const context = createContext();
const loaded = [];

for (const src of collectScriptTags()) {
  const relativePath = scriptSrcToRepoPath(src);
  if (!relativePath) continue;
  const absolutePath = resolve(repoRoot, relativePath);
  const source = readFileSync(absolutePath, "utf-8");
  try {
    new vm.Script(source, { filename: relativePath }).runInContext(context);
    loaded.push(relativePath);
  } catch (error) {
    console.error(`Failed while loading ${relativePath}`);
    throw error;
  }
}

const missing = requiredGlobals.filter((name) => context[name] === undefined);
const missingHandlers = [
  ["mediaPipelineQueueView", "renderQueueRows"],
  ["mediaPipelineQueueView", "resetQueueFilters"],
  ["mediaPipelineNetworkView", "renderNetworkView"],
].filter(([namespace, handler]) => typeof context[namespace]?.[handler] !== "function");
if (missing.length || missingHandlers.length) {
  console.error(`Missing expected globals after ordered script load: ${missing.join(", ")}`);
  if (missingHandlers.length) {
    console.error(`Missing expected namespaced handlers after ordered script load: ${missingHandlers.map(([namespace, handler]) => `${namespace}.${handler}`).join(", ")}`);
  }
  process.exitCode = 1;
} else {
  console.log(`Loaded ${loaded.length} WebView scripts in index order.`);
  console.log(`Verified globals: ${requiredGlobals.join(", ")}`);
}
