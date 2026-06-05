import { createRequire } from "node:module";

const requireFromRoot = createRequire(import.meta.url);
const requireFromOps = createRequire(new URL("./ops/scripts/dev/webview-tooling-common.mjs", import.meta.url));

function requirePackage(name) {
  try {
    return requireFromRoot(name);
  } catch (error) {
    if (error?.code !== "MODULE_NOT_FOUND") throw error;
    return requireFromOps(name);
  }
}

const js = requirePackage("@eslint/js");
const globals = requirePackage("globals");

export default [
  {
    ignores: [
      "node_modules/**",
      "apps/desktop/tauri/**",
      "apps/desktop/runtime/**",
      "LocalBase/**",
      "RunLogs/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["apps/desktop/webview/static/assets/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        __MEDIA_PIPELINE_BOOTSTRAP__: "readonly",
        byId: "readonly",
        setText: "readonly",
        setTextState: "readonly",
        apiGet: "readonly",
        apiPost: "readonly",
        appendCells: "readonly",
        appendCommandResult: "readonly",
        clearRows: "readonly",
        filterRows: "readonly",
        makeRowSelectable: "readonly",
        makeStatusChip: "readonly",
        setCellStatusChip: "readonly",
        updateTableStatusLegend: "readonly",
        formatProgressValue: "readonly",
        formatConfigValue: "readonly",
        formatPathLeaf: "readonly",
        formatBytes: "readonly",
        formatPercent: "readonly",
        jsonDetailText: "readonly",
      },
    },
    rules: {
      "complexity": ["warn", { "max": 35 }],
      "max-lines-per-function": ["warn", {
        "max": 220,
        "skipBlankLines": true,
        "skipComments": true
      }],
      "no-unused-vars": ["warn", {
        "args": "none",
        "varsIgnorePattern": "^_|Module$",
        "caughtErrors": "none"
      }],
      "no-undef": "warn",
      "no-empty": ["error", { "allowEmptyCatch": true }],
      "no-extra-boolean-cast": "warn",
      "no-unreachable": "warn",
    },
  },
];
