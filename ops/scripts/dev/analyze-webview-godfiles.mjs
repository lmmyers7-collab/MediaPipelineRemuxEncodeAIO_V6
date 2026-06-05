import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { parse } from "@babel/parser";
import traverseModule from "@babel/traverse";
import { repoRoot } from "./webview-tooling-common.mjs";

const traverse = traverseModule.default || traverseModule;
const defaultFiles = [
  "apps/desktop/webview/static/assets/app.js",
  "apps/desktop/webview/static/assets/settingsView.js",
];
const defaultReport = "docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md";

function repoRelative(path) {
  return relative(repoRoot, resolve(repoRoot, path)).replaceAll("\\", "/");
}

function parseArgs(argv) {
  const args = {
    files: [...defaultFiles],
    output: "",
    check: false,
    json: false,
    writeDefaultReport: false,
    minCandidateLines: 80,
    maxGap: 25,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--files") {
      args.files = [];
      while (argv[i + 1] && !argv[i + 1].startsWith("--")) {
        args.files.push(argv[++i]);
      }
    } else if (arg === "--output") {
      args.output = argv[++i] || "";
    } else if (arg === "--check") {
      args.check = true;
    } else if (arg === "--json") {
      args.json = true;
    } else if (arg === "--write-default-report") {
      args.writeDefaultReport = true;
    } else if (arg === "--min-candidate-lines") {
      args.minCandidateLines = Number(argv[++i] || args.minCandidateLines);
    } else if (arg === "--max-gap") {
      args.maxGap = Number(argv[++i] || args.maxGap);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return args;
}

function uniq(values, limit = null) {
  const items = [...new Set(values.filter(Boolean))].sort();
  return limit === null ? items : items.slice(0, limit);
}

function memberName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "StringLiteral") return node.value;
  return "";
}

function windowAssignmentName(node) {
  if (node?.type !== "AssignmentExpression") return "";
  const left = node.left;
  if (left?.type !== "MemberExpression" || left.object?.type !== "Identifier" || left.object.name !== "window") {
    return "";
  }
  return memberName(left.property);
}

function stringLiteralValue(node) {
  if (node?.type === "StringLiteral") return node.value;
  if (node?.type === "TemplateLiteral" && node.expressions.length === 0) return node.quasis[0]?.value?.cooked || "";
  return "";
}

function routeFromCall(path) {
  const callee = path.node.callee;
  let name = "";
  if (callee?.type === "Identifier") name = callee.name;
  if (callee?.type === "MemberExpression") name = memberName(callee.property);
  if (!["apiGet", "apiPost", "fetch"].includes(name)) return "";
  const value = stringLiteralValue(path.node.arguments?.[0]);
  return value.startsWith("/api/") ? value : "";
}

function domIdFromCall(path) {
  const callee = path.node.callee;
  let name = "";
  if (callee?.type === "Identifier") name = callee.name;
  if (callee?.type === "MemberExpression") name = memberName(callee.property);
  if (!["byId", "getElementById", "querySelector", "querySelectorAll"].includes(name)) return "";
  const value = stringLiteralValue(path.node.arguments?.[0]);
  if (!value) return "";
  if (name === "querySelector" || name === "querySelectorAll") {
    const match = value.match(/^#([A-Za-z][\w:-]*)$/);
    return match ? match[1] : "";
  }
  return value;
}

function eventFromCall(path) {
  const callee = path.node.callee;
  if (callee?.type !== "MemberExpression" || memberName(callee.property) !== "addEventListener") return "";
  return stringLiteralValue(path.node.arguments?.[0]);
}

function declarationName(path) {
  const node = path.node;
  if (node.type === "FunctionDeclaration") return node.id?.name || "";
  if (node.type === "VariableDeclaration" && node.declarations.length === 1) {
    const declaration = node.declarations[0];
    if (declaration.id?.type === "Identifier") return declaration.id.name;
  }
  return "";
}

function declarationKind(path) {
  if (path.node.type === "FunctionDeclaration") return "function";
  if (path.node.type === "VariableDeclaration") return path.node.kind;
  return path.node.type;
}

function isTopLevelDeclaration(path) {
  if (path.parentPath?.isProgram()) return true;
  if (
    path.parentPath?.isBlockStatement()
    && path.parentPath.parentPath?.isFunctionExpression()
    && path.parentPath.parentPath.parentPath?.isCallExpression()
    && path.parentPath.parentPath.parentPath.parentPath?.isExpressionStatement()
  ) {
    return true;
  }
  return false;
}

function topicFor(name, file) {
  const lower = name.toLowerCase();
  if (file.endsWith("settingsView.js")) {
    if (name.includes("FinalLibraryPromotion")) return "settings-final-library";
    if (name.includes("MediaPolicy") || name.includes("BdpgsOcr")) return "settings-media-policy";
    if (lower.startsWith("settingspatch") || lower.startsWith("settingssave")) return "settings-patch-review";
    if (lower.startsWith("settingslaunch")) return "settings-policy-impact";
    if (lower.startsWith("settingsbackend") || lower.startsWith("settingsprogress") || lower.startsWith("rendersettingsbackend") || lower.startsWith("rendersettingssaveprogress")) return "settings-backend-result";
    if (lower.startsWith("rendersettings")) return "settings-render-core";
    return "settings-core";
  }
  if (lower.startsWith("topbar")) return "topbar";
  if (lower.startsWith("closereadiness") || lower.startsWith("formatclosereadiness")) return "app-lifecycle";
  if (lower.startsWith("backendlifecycle") || lower.startsWith("tauribackendlifecycle") || lower.startsWith("renderbackend") || lower.startsWith("requestbackend")) return "app-lifecycle";
  if (lower.startsWith("refresh") || lower.startsWith("attachrefresh")) return "app-refresh";
  if (lower.startsWith("home") || lower.startsWith("daily") || lower.startsWith("externaldependency")) return "app-home";
  if (lower.startsWith("_layout") || lower.startsWith("initlayout") || lower.startsWith("_panelkey")) return "app-layout-manager";
  return "app-core";
}

function analyzeDeclaration(path, localNames, source, file) {
  const name = declarationName(path);
  const startLine = path.node.loc?.start?.line || 1;
  const endLine = path.node.loc?.end?.line || startLine;
  const used = new Set();
  const routes = [];
  const domIds = [];
  const events = [];

  path.traverse({
    Identifier(inner) {
      used.add(inner.node.name);
    },
    CallExpression(inner) {
      routes.push(routeFromCall(inner));
      domIds.push(domIdFromCall(inner));
      events.push(eventFromCall(inner));
    },
  });

  const text = source.split(/\r?\n/).slice(startLine - 1, endLine).join("\n");
  const windowExports = [...text.matchAll(/\bwindow\.([A-Za-z_$][\w$]*)\s*=/g)].map((match) => match[1]);

  return {
    name,
    kind: declarationKind(path),
    topic: topicFor(name, file),
    startLine,
    endLine,
    lineCount: endLine - startLine + 1,
    dependsOnLocal: uniq([...used].filter((item) => localNames.has(item) && item !== name), 40),
    apiRoutes: uniq(routes),
    domIds: uniq(domIds),
    events: uniq(events),
    windowExports: uniq(windowExports),
  };
}

function buildCandidates(declarations, file, minLines, maxGap) {
  const candidates = [];
  let group = [];

  function suggestedFileForTopic(sourcePath, stem, topic) {
    const dir = sourcePath.join("/");
    const names = {
      app: {
        "app-lifecycle": "app.lifecycle.js",
        "app-refresh": "app.refresh.js",
        "app-home": "app.home.js",
        "app-layout-manager": "app.layoutManager.js",
        "app-core": "app.core.js",
        topbar: "app.topbar.js",
      },
      settingsView: {
        "settings-backend-result": "settingsView.backendResult.js",
        "settings-patch-review": "settingsView.patchReview.js",
        "settings-policy-impact": "settingsView.policyImpact.js",
        "settings-media-policy": "settingsView.policyImpact.js",
        "settings-final-library": "settingsView.policyImpact.js",
        "settings-render-core": "settingsView.renderCore.js",
        "settings-core": "settingsView.core.js",
      },
    };
    const fileName = names[stem]?.[topic] || `${stem}.${topic.replace(/^app-|^settings-/, "")}.js`;
    return `${dir}/${fileName}`;
  }

  function flush() {
    if (!group.length) return;
    const start = group[0].startLine;
    const end = group[group.length - 1].endLine;
    const lineCount = end - start + 1;
    if (lineCount >= minLines) {
      const names = new Set(group.map((item) => item.name));
      const topic = group[0].topic;
      const sourcePath = file.split("/");
      const fileName = sourcePath.pop();
      const stem = fileName.replace(/\.js$/, "");
      candidates.push({
        topic,
        startLine: start,
        endLine: end,
        lineCount,
        declarations: group.map((item) => item.name),
        dependsOnLocalOutsideSlice: uniq(group.flatMap((item) => item.dependsOnLocal).filter((item) => !names.has(item)), 30),
        apiRoutes: uniq(group.flatMap((item) => item.apiRoutes), 30),
        domIds: uniq(group.flatMap((item) => item.domIds), 40),
        events: uniq(group.flatMap((item) => item.events), 20),
        suggestedFile: suggestedFileForTopic(sourcePath, stem, topic),
      });
    }
    group = [];
  }

  for (const declaration of declarations) {
    const previous = group[group.length - 1];
    if (!previous || (previous.topic === declaration.topic && declaration.startLine - previous.endLine <= maxGap)) {
      group.push(declaration);
      continue;
    }
    flush();
    group.push(declaration);
  }
  flush();
  return candidates.sort((left, right) => right.lineCount - left.lineCount);
}

function analyzeFile(file, options) {
  const absolute = resolve(repoRoot, file);
  const source = readFileSync(absolute, "utf-8");
  const ast = parse(source, {
    sourceType: "script",
    errorRecovery: true,
    plugins: ["optionalChaining", "nullishCoalescingOperator"],
  });
  const declarationPaths = [];
  const localNames = new Set();
  const windowExports = [];
  const routes = [];
  const domIds = [];
  const events = [];

  traverse(ast, {
    FunctionDeclaration(path) {
      if (!isTopLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) {
        declarationPaths.push(path);
        localNames.add(name);
      }
    },
    VariableDeclaration(path) {
      if (!isTopLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) {
        declarationPaths.push(path);
        localNames.add(name);
      }
    },
    AssignmentExpression(path) {
      windowExports.push(windowAssignmentName(path.node));
    },
    CallExpression(path) {
      routes.push(routeFromCall(path));
      domIds.push(domIdFromCall(path));
      events.push(eventFromCall(path));
    },
  });

  const rel = repoRelative(file);
  const declarations = declarationPaths
    .map((path) => analyzeDeclaration(path, localNames, source, rel))
    .sort((left, right) => left.startLine - right.startLine);
  const referencedBy = new Map(declarations.map((item) => [item.name, []]));
  for (const declaration of declarations) {
    for (const dependency of declaration.dependsOnLocal) {
      if (referencedBy.has(dependency)) referencedBy.get(dependency).push(declaration.name);
    }
  }
  declarations.forEach((declaration) => {
    declaration.referencedByLocal = uniq(referencedBy.get(declaration.name) || [], 40);
  });

  const lines = source.split(/\r?\n/);
  return {
    path: rel,
    lineCount: lines.length,
    nonblankLineCount: lines.filter((line) => line.trim()).length,
    declarationCount: declarations.length,
    namespaceExports: uniq(windowExports.filter((name) => name.startsWith("mediaPipeline"))),
    flatExports: uniq(windowExports.filter((name) => name && !name.startsWith("mediaPipeline"))),
    apiRoutes: uniq(routes),
    domIds: uniq(domIds),
    events: uniq(events),
    declarations,
    candidates: buildCandidates(declarations, rel, options.minCandidateLines, options.maxGap),
  };
}

function codeList(values, limit = 8) {
  if (!values?.length) return "-";
  const shown = values.slice(0, limit).map((item) => `\`${item}\``).join(", ");
  return values.length > limit ? `${shown} (+${values.length - limit})` : shown;
}

function renderMarkdown(analyses, options) {
  const lines = [
    "# WEBVIEW_GODFILE_SPLIT_MAP",
    "",
    "Generated by `ops/scripts/dev/analyze-webview-godfiles.mjs`. Do not hand-edit.",
    "",
    "This report maps large plain-script WebView assets before split work. It is analysis only; it does not rewrite source.",
    `Candidate slices require at least **${options.minCandidateLines}** contiguous lines with gaps of **${options.maxGap}** lines or fewer.`,
    "",
  ];
  for (const analysis of analyses) {
    lines.push(`## \`${analysis.path}\``, "");
    lines.push(`- Lines: **${analysis.lineCount}** (${analysis.nonblankLineCount} nonblank)`);
    lines.push(`- Top-level declarations: **${analysis.declarationCount}**`);
    lines.push(`- Namespace exports: ${codeList(analysis.namespaceExports, 12)}`);
    lines.push(`- Flat compatibility exports: **${analysis.flatExports.length}**`);
    lines.push(`- API routes: ${codeList(analysis.apiRoutes, 14)}`);
    lines.push(`- DOM IDs touched: **${analysis.domIds.length}**`);
    lines.push(`- Event types: ${codeList(analysis.events, 14)}`);
    lines.push("", "### Candidate Slices", "");
    lines.push("| Lines | Topic | Declarations | Outside local deps | API routes | Suggested file |");
    lines.push("|---:|---|---|---|---|---|");
    for (const candidate of analysis.candidates.slice(0, 30)) {
      lines.push(
        `| ${candidate.startLine}-${candidate.endLine} (${candidate.lineCount}) `
        + `| \`${candidate.topic}\` `
        + `| ${codeList(candidate.declarations, 7)} `
        + `| ${codeList(candidate.dependsOnLocalOutsideSlice, 5)} `
        + `| ${codeList(candidate.apiRoutes, 5)} `
        + `| \`${candidate.suggestedFile}\` |`
      );
    }
    lines.push("", "### Largest Declarations", "");
    lines.push("| Lines | Name | Topic | Local deps | Referenced by |");
    lines.push("|---:|---|---|---|---|");
    for (const declaration of [...analysis.declarations].sort((left, right) => right.lineCount - left.lineCount).slice(0, 40)) {
      lines.push(
        `| ${declaration.startLine}-${declaration.endLine} (${declaration.lineCount}) `
        + `| \`${declaration.name}\` `
        + `| \`${declaration.topic}\` `
        + `| ${codeList(declaration.dependsOnLocal, 5)} `
        + `| ${codeList(declaration.referencedByLocal, 5)} |`
      );
    }
    lines.push("");
  }
  return `${lines.join("\n").trim()}\n`;
}

function writeOrCheck(path, content, check) {
  const absolute = resolve(repoRoot, path);
  if (check) {
    const current = existsSync(absolute) ? readFileSync(absolute, "utf-8") : "";
    if (current === content) {
      console.log(`${repoRelative(path)} is current`);
      return 0;
    }
    console.error(`${repoRelative(path)} is stale. Run npm run webview:map.`);
    return 1;
  }
  mkdirSync(dirname(absolute), { recursive: true });
  writeFileSync(absolute, content, "utf-8");
  console.log(`Wrote ${repoRelative(path)}`);
  return 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const analyses = args.files.map((file) => analyzeFile(file, args));
  const content = args.json ? `${JSON.stringify(analyses, null, 2)}\n` : renderMarkdown(analyses, args);
  const output = args.writeDefaultReport || args.check ? defaultReport : args.output;
  if (output) return writeOrCheck(output, content, args.check);
  process.stdout.write(content);
  return 0;
}

process.exitCode = main();
