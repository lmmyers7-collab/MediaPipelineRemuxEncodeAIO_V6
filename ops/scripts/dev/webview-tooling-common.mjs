import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@babel/parser";
import traverseModule from "@babel/traverse";

export const traverse = traverseModule.default || traverseModule;
export const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
export const webviewStaticRoot = join(repoRoot, "apps", "desktop", "webview", "static");
export const webviewAssetsRoot = join(webviewStaticRoot, "assets");
export const webviewIndexPath = join(webviewStaticRoot, "index.html");

export function repoRelative(path) {
  return relative(repoRoot, resolve(repoRoot, path)).replaceAll("\\", "/");
}

export function readText(path) {
  return readFileSync(resolve(repoRoot, path), "utf-8");
}

export function sortedUniq(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

export function collectJsFiles(dir = webviewAssetsRoot) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(repoRelative(fullPath));
    }
  }
  return files.sort();
}

export function collectScriptTags(indexHtml = readFileSync(webviewIndexPath, "utf-8")) {
  return [...indexHtml.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)]
    .map((match) => match[1])
    .filter(Boolean);
}

export function scriptSrcToRepoPath(src) {
  const normalized = src.split(/[?#]/, 1)[0].replace(/^\//, "");
  if (!normalized.startsWith("assets/")) return "";
  return repoRelative(join(webviewStaticRoot, normalized));
}

export function collectHtmlIds(indexHtml = readFileSync(webviewIndexPath, "utf-8")) {
  return sortedUniq([...indexHtml.matchAll(/\bid=["']([^"']+)["']/gi)].map((match) => match[1]));
}

function memberName(node) {
  if (!node) return "";
  if (node.type === "Identifier") return node.name;
  if (node.type === "StringLiteral") return node.value;
  return "";
}

function stringLiteralValue(node) {
  if (node?.type === "StringLiteral") return node.value;
  if (node?.type === "TemplateLiteral" && node.expressions.length === 0) return node.quasis[0]?.value?.cooked || "";
  return "";
}

function assignmentToWindowName(node) {
  if (node?.type !== "AssignmentExpression") return "";
  const left = node.left;
  if (left?.type !== "MemberExpression" || left.object?.type !== "Identifier" || left.object.name !== "window") return "";
  return memberName(left.property);
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

export function declarationName(path) {
  const node = path.node;
  if (node.type === "FunctionDeclaration") return node.id?.name || "";
  if (node.type === "VariableDeclaration" && node.declarations.length === 1) {
    const declaration = node.declarations[0];
    if (declaration.id?.type === "Identifier") return declaration.id.name;
  }
  return "";
}

export function isScriptLevelDeclaration(path) {
  if (path.parentPath?.isProgram()) return true;
  return Boolean(
    path.parentPath?.isBlockStatement()
      && path.parentPath.parentPath?.isFunctionExpression()
      && path.parentPath.parentPath.parentPath?.isCallExpression()
      && path.parentPath.parentPath.parentPath.parentPath?.isExpressionStatement()
  );
}

export function parseScript(source, pathForErrors = "script.js") {
  const ast = parse(source, {
    sourceFilename: pathForErrors,
    sourceType: "script",
    errorRecovery: true,
    plugins: ["optionalChaining", "nullishCoalescingOperator"],
  });
  const recoverableErrors = ast.errors || [];
  if (recoverableErrors.length) {
    const details = recoverableErrors
      .map((error) => {
        const location = error.loc ? `${error.loc.line}:${error.loc.column}` : "unknown";
        return `${location} ${error.message}`;
      })
      .join("; ");
    throw new SyntaxError(`Recoverable parser error in ${pathForErrors}: ${details}`);
  }
  return ast;
}

export function analyzeScriptAsset(relativePath) {
  const source = readText(relativePath);
  const ast = parseScript(source, relativePath);
  const topLevelDeclarations = [];
  const windowExports = [];
  const apiRoutes = [];
  const domIds = [];
  const events = [];

  traverse(ast, {
    FunctionDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) topLevelDeclarations.push({ name, line: path.node.loc?.start?.line || 1, kind: "function" });
    },
    VariableDeclaration(path) {
      if (!isScriptLevelDeclaration(path)) return;
      const name = declarationName(path);
      if (name) topLevelDeclarations.push({ name, line: path.node.loc?.start?.line || 1, kind: path.node.kind });
    },
    AssignmentExpression(path) {
      windowExports.push(assignmentToWindowName(path.node));
    },
    CallExpression(path) {
      apiRoutes.push(routeFromCall(path));
      domIds.push(domIdFromCall(path));
      events.push(eventFromCall(path));
    },
  });

  const uniqueWindowExports = sortedUniq(windowExports);
  return {
    path: relativePath,
    top_level_declarations: topLevelDeclarations.sort((left, right) => left.line - right.line || left.name.localeCompare(right.name)),
    namespace_exports: uniqueWindowExports.filter((name) => name.startsWith("mediaPipeline")),
    flat_window_exports: uniqueWindowExports.filter((name) => name && !name.startsWith("mediaPipeline")),
    api_routes: sortedUniq(apiRoutes),
    dom_ids_touched: sortedUniq(domIds),
    event_types: sortedUniq(events),
  };
}

export function writeOrCheckText(outputPath, content, check) {
  const absolute = resolve(repoRoot, outputPath);
  if (check) {
    const current = existsSync(absolute) ? readFileSync(absolute, "utf-8") : "";
    if (current === content) {
      console.log(`${repoRelative(outputPath)} is current`);
      return 0;
    }
    console.error(`${repoRelative(outputPath)} is stale`);
    return 1;
  }
  mkdirSync(dirname(absolute), { recursive: true });
  writeFileSync(absolute, content, "utf-8");
  console.log(`Wrote ${repoRelative(outputPath)}`);
  return 0;
}

export function writeOrCheckJson(outputPath, value, check) {
  return writeOrCheckText(outputPath, `${JSON.stringify(value, null, 2)}\n`, check);
}
