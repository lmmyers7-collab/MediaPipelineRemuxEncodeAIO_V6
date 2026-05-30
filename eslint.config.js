import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: [
      "node_modules/**",
      "DesktopApp/tauri_shell/**",
      "DesktopApp/Runtime/**",
      "LocalBase/**",
      "RunLogs/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/**/*.js"],
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
