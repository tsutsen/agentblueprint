import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import util from "node:util";

export const execFilePromise = util.promisify(execFile);

/**
 * Resolve the python command to use: prefer .venv if available, fall back to system python.
 */
export function resolvePython(cwd: string): string {
  const venvPython = path.resolve(cwd, '.venv/bin/python');
  return fs.existsSync(venvPython) ? venvPython : 'python';
}

// --- JSON Schema validation (via Python jsonschema) ---

export async function validateAgainstSchema(
  json: any,
  schemaPath: string,
): Promise<{ valid: boolean; errors: string[] }> {
  const escaped = schemaPath.replace(/"/g, '\\"');
  const script = `
import json, sys
try:
    import jsonschema
except ImportError:
    print("jsonschema not installed", file=sys.stderr)
    sys.exit(2)
schema = json.loads(open("${escaped}").read())
data = json.loads(sys.stdin.read())
v = jsonschema.Draft7Validator(schema)
errors = [e.message for e in v.iter_errors(data)]
if errors:
    print(json.dumps({"valid": False, "errors": errors}))
else:
    print(json.dumps({"valid": True, "errors": []}))
`;
  try {
    const { stdout } = await execFilePromise('python', ['-c', script], {
      input: JSON.stringify(json),
      timeout: 10000,
    });
    const result = JSON.parse(stdout);
    return { valid: result.valid, errors: result.errors || [] };
  } catch (err: any) {
    return { valid: false, errors: [err.message || 'jsonschema validation failed'] };
  }
}

// --- Frontmatter helpers ---

export function extractFrontmatter(text: string): Record<string, string> {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return {};
  const fm: Record<string, string> = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^(\w+):\s*(.+)$/);
    if (kv) fm[kv[1]] = kv[2].trim();
  }
  return fm;
}

// ── Dependency graph ────────────────────────────────────────────────────────

export interface DepDef {
  name: string;           // Human-readable name, e.g. "GoalSpec"
  jsonPath: string;       // e.g. "artifacts/GoalSpec.json"
  mdPath: string;         // e.g. "artifacts/GoalSpec.md"
  required: boolean;      // Whether loading fails if missing
}

/**
 * Mapping from schema specDependencies keys to DEPS format.
 * Single source of truth: DEPS is derived from these + schema specDependencies.
 */
export const SCHEMA_NAME_MAP: Record<string, { key: string; schemaFile: string; schemaFileName: string }> = {
  goal: { key: "GoalSpec", schemaFile: "GoalSpec.md", schemaFileName: "goalspec.schema.json" },
  glossary: { key: "Glossary", schemaFile: "Glossary.md", schemaFileName: "glossary.schema.json" },
  design: { key: "DesignSpec", schemaFile: "DesignSpec.md", schemaFileName: "designspec.schema.json" },
  arch: { key: "ArchitectureSpec", schemaFile: "ArchitectureSpec.md", schemaFileName: "archspec.schema.json" },
  data: { key: "DataSpec", schemaFile: "DataSpec.md", schemaFileName: "dataspec.schema.json" },
  api: { key: "ApiSpec", schemaFile: "ApiSpec.md", schemaFileName: "apispec.schema.json" },
  test: { key: "TestSpec", schemaFile: "TestSpec.md", schemaFileName: "testspec.schema.json" },
  plan: { key: "TaskPlan", schemaFile: "TaskPlan.md", schemaFileName: "taskplan.schema.json" },
  issues: { key: "Issue", schemaFile: "Issue.md", schemaFileName: "issue.schema.json" },
};

/**
 * Map a schema dependency name (e.g. "goalSpec", "glossary") to a DepDef.
 * Falls back to a default path pattern when the name is unknown.
 */
export function schemaDepToDepDef(depName: string, required: boolean): DepDef {
  const nameMap: Record<string, DepDef> = {
    goalSpec: { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required },
    glossary: { name: "Glossary", jsonPath: "artifacts/Glossary.json", mdPath: "artifacts/Glossary.md", required },
    designSpec: { name: "Design", jsonPath: "artifacts/DesignSpec.json", mdPath: "artifacts/DesignSpec.md", required },
    architectureSpec: { name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md", required },
    dataSpec: { name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md", required },
    apiSpec: { name: "ApiSpec", jsonPath: "artifacts/ApiSpec.json", mdPath: "artifacts/ApiSpec.md", required },
    testSpec: { name: "TestSpec", jsonPath: "artifacts/TestSpec.json", mdPath: "artifacts/TestSpec.md", required },
    taskPlan: { name: "TaskPlan", jsonPath: "", mdPath: "tasks/PLAN.md", required },
    epic: { name: "Epic", jsonPath: "", mdPath: "tasks/epics/", required },
  };
  return nameMap[depName] ?? { name: depName, jsonPath: "", mdPath: "", required };
}

/**
 * Build the DEPS object by reading specDependencies from schema files.
 * Falls back to hardcoded defaults if schema files can't be read.
 */
export function loadDepsFromSchemas(): Record<string, { schema: string; dependencies: DepDef[] }> {
  const schemasDir = path.join(__dirname, "..", "..", "skills", "blueprint", "schemas", "json");
  const result: Record<string, { schema: string; dependencies: DepDef[] }> = {};

  for (const [key, info] of Object.entries(SCHEMA_NAME_MAP)) {
    const schemaPath = path.join(schemasDir, info.schemaFileName);
    let deps: DepDef[] = [];

    try {
      const raw = fs.readFileSync(schemaPath, "utf-8");
      const schema = JSON.parse(raw);
      const specDeps = (schema as Record<string, any>).specDependencies ?? {};
      for (const [depName, depInfo] of Object.entries(specDeps)) {
        const required = (depInfo as Record<string, any>).required !== false;
        deps.push(schemaDepToDepDef(depName, required));
      }
    } catch {
      // Schema file missing or unreadable — deps stay empty
    }

    result[key] = { schema: info.schemaFile, dependencies: deps };
  }

  return result;
}

export const DEPS = loadDepsFromSchemas();

// ── Path resolution helpers ─────────────────────────────────────────────────

export function resolveSchemaPath(extDir: string, schemaName: string): string {
  const packageRoot = path.join(extDir, '..', '..');
  return path.join(packageRoot, 'skills', 'blueprint', 'schemas', `${schemaName}.schema.json`);
}

export function resolvePkgResource(extDir: string, relPath: string): string {
  const packageRoot = path.join(extDir, '..', '..');
  return path.join(packageRoot, relPath);
}

// Helper to map artifact name to command key
export function resolveCommand(name: string): string {
  const map: Record<string, string> = {
    GoalSpec: "goal",
    Glossary: "glossary",
    DesignSpec: "design",
    ArchitectureSpec: "arch",
    DataSpec: "data",
    ApiSpec: "api",
    TestSpec: "test",
  };
  return map[name] || name;
}

// Helper to read frontmatter
export function readFrontmatter(content: string): Record<string, string> {
  const fm: Record<string, string> = {};
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return fm;
  for (const line of match[1].split('\n')) {
    const kv = line.match(/^(.+?):\s*(.+)$/);
    if (kv) fm[kv[1].trim()] = kv[2].trim();
  }
  return fm;
}

// ── Helper: Resolve package paths (works in dev and installed modes) ───────

export function resolvePackagePaths(cwd: string) {
  const paths = {
    // Development mode: .pi/extensions/blueprint/
    devExtDir: path.resolve(cwd, ".pi/extensions/blueprint"),
    devSchemasSrc: path.resolve(cwd, ".pi/skills/blueprint/instructions"),
    // Installed package mode: node_modules/@agentblueprint/blueprint/
    pkgExtDir: path.resolve(cwd, "node_modules/@agentblueprint/blueprint/extensions/blueprint"),
    pkgSchemasSrc: path.resolve(cwd, "node_modules/@agentblueprint/blueprint/skills/blueprint/instructions"),
  };

  // Prefer development mode if .pi/ exists
  if (fs.existsSync(paths.devExtDir) || fs.existsSync(paths.devSchemasSrc)) {
    return { ...paths, mode: "dev", extDir: paths.devExtDir, schemasSrc: paths.devSchemasSrc };
  }

  // Fall back to installed package mode
  if (fs.existsSync(paths.pkgExtDir) || fs.existsSync(paths.pkgSchemasSrc)) {
    return { ...paths, mode: "pkg", extDir: paths.pkgExtDir, schemasSrc: paths.pkgSchemasSrc };
  }

  // Neither mode found — return dev paths (will fail gracefully if missing)
  return { ...paths, mode: "none", extDir: paths.devExtDir, schemasSrc: paths.devSchemasSrc };
}
