import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import util from "node:util";

const execFilePromise = util.promisify(execFile);

// --- JSON Schema validation (via Python jsonschema) ---

async function validateAgainstSchema(
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

function extractFrontmatter(text: string): Record<string, string> {
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

interface DepDef {
  name: string;           // Human-readable name, e.g. "GoalSpec"
  jsonPath: string;       // e.g. "artifacts/GoalSpec.json"
  mdPath: string;         // e.g. "artifacts/GoalSpec.md"
  required: boolean;      // Whether loading fails if missing
}

const DEPS: Record<string, { schema: string; dependencies: DepDef[] }> = {
  goal: {
    schema: "GoalSpec.md",
    dependencies: [],
  },
  glossary: {
    schema: "Glossary.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
    ],
  },
  design: {
    schema: "DesignSpec.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "Glossary", jsonPath: "artifacts/Glossary.json", mdPath: "artifacts/Glossary.md", required: true },
    ],
  },
  arch: {
    schema: "ArchitectureSpec.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "Glossary", jsonPath: "artifacts/Glossary.json", mdPath: "artifacts/Glossary.md", required: true },
    ],
  },
  data: {
    schema: "DataSpec.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md", required: true },
    ],
  },
  api: {
    schema: "ApiSpec.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md", required: true },
      { name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md", required: true },
    ],
  },
  test: {
    schema: "TestSpec.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "ApiSpec", jsonPath: "artifacts/ApiSpec.json", mdPath: "artifacts/ApiSpec.md", required: true },
      { name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md", required: true },
    ],
  },
  plan: {
    schema: "TaskPlan.md",
    dependencies: [
      { name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md", required: true },
      { name: "Design", jsonPath: "artifacts/DesignSpec.json", mdPath: "artifacts/DesignSpec.md", required: true },
      { name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md", required: true },
      { name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md", required: true },
      { name: "ApiSpec", jsonPath: "artifacts/ApiSpec.json", mdPath: "artifacts/ApiSpec.md", required: true },
      { name: "TestSpec", jsonPath: "artifacts/TestSpec.json", mdPath: "artifacts/TestSpec.md", required: true },
    ],
  },
  issues: {
    schema: "Issue.md",
    dependencies: [
      { name: "TaskPlan", jsonPath: "", mdPath: "tasks/PLAN.md", required: false },
    ],
  },
};

// ── Tool: load_artifact ──────────────────────────────────────────────────────

function registerLoadArtifact(pi: ExtensionAPI) {
  pi.registerTool({
    name: "load_artifact",
    label: "Load Artifact",
    description:
      "Resolve and load an artifact's schema and dependencies. Prefers JSON " +
      "over Markdown when both exist. Validates that required dependencies " +
      "are present. Returns structured result for the blueprint orchestrator.",
    parameters: Type.Object({
      artifactType: Type.String({
        description: "Artifact type: goal, design, arch, data, api, test, glossary, plan, issues",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { artifactType } = params;
      const cwd = ctx.cwd;

      const def = DEPS[artifactType];
      if (!def) {
        return {
          content: [{ type: "text", text: `Unknown artifact type: ${artifactType}` }],
          details: { resolved: false },
          isError: true,
        };
      }

      const result: {
        schemaContent: string | null;
        schemaPath: string;
        dependencies: Array<{
          name: string;
          content: any;
          format: "json" | "markdown";
          path: string;
          resolved: boolean;
        }>;
        missing: Array<{ name: string; required: boolean; path: string }>;
        warnings: string[];
      } = {
        schemaContent: null,
        schemaPath: "",
        dependencies: [],
        missing: [],
        warnings: [],
      };

      // 1. Load schema (support both dev and installed package modes)
      const pkgPaths = resolvePackagePaths(cwd);
      let schemaPath = "";
      let schemaPathStr = "";

      if (pkgPaths.schemasSrc) {
        schemaPath = path.join(pkgPaths.schemasSrc, def.schema);
        schemaPathStr = path.posix.join(pkgPaths.mode === "dev" ? ".pi" : "node_modules/@agentblueprint/blueprint", "skills", "blueprint", "schemas", "markdown", def.schema);
      }
      result.schemaPath = schemaPathStr;
      if (fs.existsSync(schemaPath)) {
        result.schemaContent = fs.readFileSync(schemaPath, "utf-8");
      } else {
        result.warnings.push(`Schema not found: ${result.schemaPath}`);
      }

      // 2. Resolve dependencies (prefer JSON over Markdown)
      for (const dep of def.dependencies) {
        if (!dep.jsonPath && !dep.mdPath) {
          // No file to load (e.g., placeholder)
          continue;
        }

        const jsonFull = path.resolve(cwd, dep.jsonPath);
        const mdFull = path.resolve(cwd, dep.mdPath);

        if (dep.jsonPath && fs.existsSync(jsonFull)) {
          // Prefer JSON
          try {
            result.dependencies.push({
              name: dep.name,
              content: JSON.parse(fs.readFileSync(jsonFull, "utf-8")),
              format: "json",
              path: dep.jsonPath,
              resolved: true,
            });
          } catch (err: any) {
            result.warnings.push(`${dep.name}: JSON parse error — falling back to Markdown`);
            // Fall through to Markdown
          }
        }

        if (!result.dependencies.find(d => d.name === dep.name) && dep.mdPath && fs.existsSync(mdFull)) {
          // Markdown fallback
          result.dependencies.push({
            name: dep.name,
            content: fs.readFileSync(mdFull, "utf-8"),
            format: "markdown",
            path: dep.mdPath,
            resolved: true,
          });
        }

        // Check if missing
        if (!result.dependencies.find(d => d.name === dep.name)) {
          const missingPath = dep.jsonPath || dep.mdPath;
          result.missing.push({ name: dep.name, required: dep.required, path: missingPath });
        }
      }

      // 3. Check for missing required dependencies
      const requiredMissing = result.missing.filter(d => d.required);
      if (requiredMissing.length > 0) {
        const names = requiredMissing.map(d => d.name);
        return {
          content: [{
            type: "text",
            text: `Missing required dependencies: ${names.join(", ")}.\n` +
              `Cannot proceed until these artifacts are created.`,
          }],
          details: {
            resolved: false,
            missing: requiredMissing,
            warnings: result.warnings,
          },
          isError: true,
        };
      }

      // 4. Warn about optional missing dependencies
      const optionalMissing = result.missing.filter(d => !d.required);
      if (optionalMissing.length > 0) {
        result.warnings.push(
          `Optional dependencies not found: ${optionalMissing.map(d => d.name).join(", ")}`,
        );
      }

      return {
        content: [{
          type: "text",
          text: `Loaded ${def.schema}\n` +
            `  Dependencies: ${result.dependencies.length} resolved, ${result.missing.length} missing\n` +
            (result.warnings.length > 0 ? `  Warnings: ${result.warnings.join("; ")}` : ""),
        }],
        details: {
          resolved: true,
          schemaPath: result.schemaPath,
          dependencies: result.dependencies.map(d => ({
            name: d.name,
            format: d.format,
            path: d.path,
          })),
          missing: result.missing,
          warnings: result.warnings,
        },
      };
    },
  });
}

// ── Tool: dual_output ────────────────────────────────────────────────────────

function registerDualOutput(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "dual_output",
    label: "Dual Output",
    description:
      "Validate an existing JSON artifact against its schema, set the status " +
      "field from the markdown frontmatter, and write the final JSON file. " +
      "Does NOT parse markdown — the JSON must already exist (written by write_section).",
    parameters: Type.Object({
      artifactType: Type.String({
        description: "Artifact type: goal, design, arch, data, api, test, glossary, issue",
      }),
      filePath: Type.String({
        description: "Path to the markdown file (e.g. artifacts/GoalSpec.md or tasks/epics/EP-001/IS-001/IS-001.md)",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { artifactType, filePath } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const jsonPath = fullPath.replace(/\.md$/, '.json');
      const schemaName = artifactType === 'arch' ? 'archspec'
        : artifactType === 'data' ? 'data'
        : artifactType === 'api' ? 'api'
        : artifactType === 'test' ? 'test'
        : artifactType === 'design' ? 'designspec'
        : artifactType === 'glossary' ? 'glossary'
        : artifactType === 'goal' ? 'goalspec'
        : artifactType === 'issues' ? 'issue'
        : null;

      if (!schemaName) {
        return {
          content: [{ type: "text", text: `Unknown artifact type: ${artifactType}` }],
          details: { verified: false },
          isError: true,
        };
      }

      // 1. Check that JSON file already exists
      if (!fs.existsSync(jsonPath)) {
        return {
          content: [{
            type: "text",
            text: `ERROR: JSON file not found at ${jsonPath}. ` +
              `The JSON must be written during the interview via write_section. ` +
              `Run the interview first, then call dual_output.`,
          }],
          details: { verified: false },
          isError: true,
        };
      }

      // 2. Read markdown for frontmatter status
      const markdown = fs.readFileSync(fullPath, 'utf-8');
      const fm = extractFrontmatter(markdown);
      const status = fm.status || 'draft';

      // 3. Read and parse JSON
      let json: any;
      try {
        json = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `ERROR: invalid JSON at ${jsonPath}: ${err.message}` }],
          details: { verified: false },
          isError: true,
        };
      }

      // 4. Validate against schema — resolve relative to package root, not extDir
      const schemaPath = resolveSchemaPath(extDir, schemaName);
      const validation = await validateAgainstSchema(json, schemaPath);

      if (!validation.valid) {
        return {
          content: [{
            type: "text",
            text: `JSON validation failed:\n${validation.errors.map(e => `  ✗ ${e}`).join('\n')}\n\n` +
              `Fix the JSON artifact and run dual_output again.`,
          }],
          details: { verified: false, validationErrors: validation.errors },
          isError: true,
        };
      }

      // 5. Set status from frontmatter
      json.status = status;

      // 6. Write JSON
      fs.writeFileSync(jsonPath, JSON.stringify(json, null, 2) + '\n');

      // 7. Verify
      const written = fs.readFileSync(jsonPath, 'utf-8');
      const revalidated = JSON.parse(written);
      const hasStatus = revalidated.status === status;

      if (!hasStatus) {
        return {
          content: [{ type: "text", text: `ERROR: status not set correctly in JSON.` }],
          details: { verified: false },
          isError: true,
        };
      }

      return {
        content: [{
          type: "text",
          text: `Dual output complete: ${jsonPath}\n` +
            `  status: ${json.status}\n` +
            `  schema validation: passed`,
        }],
        details: {
          verified: true,
          path: jsonPath,
          status: json.status,
          validationErrors: [],
        },
      };
    },
  });
}

// ── Tool: handoff ────────────────────────────────────────────────────────────

function registerHandoff(pi: ExtensionAPI) {
  pi.registerTool({
    name: "handoff",
    label: "Handoff",
    description:
      "Produce a handoff table listing all artifacts whose dependencies are " +
      "met. Reads frontmatter from each artifact to report accurate status.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const cwd = ctx.cwd;

      // Map of command -> artifact name -> expected JSON file
      const artifactOrder = [
        { command: "goal", name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md" },
        { command: "glossary", name: "Glossary", jsonPath: "artifacts/Glossary.json", mdPath: "artifacts/Glossary.md" },
        { command: "design", name: "Design", jsonPath: "artifacts/DesignSpec.json", mdPath: "artifacts/DesignSpec.md" },
        { command: "arch", name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md" },
        { command: "data", name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md" },
        { command: "api", name: "ApiSpec", jsonPath: "artifacts/ApiSpec.json", mdPath: "artifacts/ApiSpec.md" },
        { command: "test", name: "TestSpec", jsonPath: "artifacts/TestSpec.json", mdPath: "artifacts/TestSpec.md" },
        { command: "plan", name: "TaskPlan", jsonPath: "", mdPath: "tasks/PLAN.md" }, // plan produces tasks/PLAN.md, not artifacts/
      ];

      // Build set of completed artifacts (JSON exists)
      const completed: Set<string> = new Set();
      for (const art of artifactOrder) {
        if (art.jsonPath && fs.existsSync(path.resolve(cwd, art.jsonPath))) {
          completed.add(art.command);
        }
      }

      // Check dependencies and build handoff list
      const available: Array<{ command: string; name: string; status: string }> = [];

      for (const art of artifactOrder) {
        if (art.command === "plan") continue; // plan handled separately

        const deps = DEPS[art.command]?.dependencies || [];
        const missingDeps = deps.filter(d => d.required && !completed.has(resolveCommand(d.name)));

        if (missingDeps.length > 0) continue;

        // Read frontmatter for status
        let status = "in_progress";
        if (art.mdPath && fs.existsSync(path.resolve(cwd, art.mdPath))) {
          const fm = readFrontmatter(fs.readFileSync(path.resolve(cwd, art.mdPath), "utf-8"));
          status = fm.status || "in_progress";
        }

        available.push({ command: art.command, name: art.name, status });
      }

      // Check if plan is available
      let planAvailable = false;
      const planDeps = DEPS.plan?.dependencies || [];
      const planMissing = planDeps.filter(d => d.required && !completed.has(resolveCommand(d.name)));
      if (planMissing.length === 0 && fs.existsSync(path.resolve(cwd, "tasks/PLAN.md"))) {
        planAvailable = true;
      }

      // Build output
      if (available.length === 0 && !planAvailable) {
        return {
          content: [{ type: "text", text: "No artifacts ready for handoff yet. Complete the current artifact first." }],
          details: { available: [] },
        };
      }

      const nextSteps = available.map(a => {
        const statusLabel = a.status === "complete" ? "complete" : a.status === "needs_review" ? "needs_review" : "in_progress";
        return `| ${a.name} | /skill:blueprint ${a.command} | ${statusLabel} |`;
      });

      if (planAvailable) {
        nextSteps.push(`| TaskPlan | /skill:blueprint plan | complete |`);
      }

      const output = `\`artifacts/<ArtifactType>.json\` is complete.\n\nYou can now proceed to:\n\n| Next step | Command | Status |\n|---|---|---|\n${nextSteps.join('\n')}\n\nOpen a fresh session for each next step.`;

      return {
        content: [{ type: "text", text: output }],
        details: { available, planAvailable },
      };
    },
  });
}

// Helper to map artifact name to command key
function resolveCommand(name: string): string {
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
function readFrontmatter(content: string): Record<string, string> {
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

function resolvePackagePaths(cwd: string) {
  const paths = {
    // Development mode: .pi/extensions/blueprint/
    devExtDir: path.resolve(cwd, ".pi/extensions/blueprint"),
    devSchemasSrc: path.resolve(cwd, ".pi/skills/blueprint/schemas/markdown"),
    // Installed package mode: node_modules/@agentblueprint/blueprint/
    pkgExtDir: path.resolve(cwd, "node_modules/@agentblueprint/blueprint/extensions/blueprint"),
    pkgSchemasSrc: path.resolve(cwd, "node_modules/@agentblueprint/blueprint/skills/blueprint/schemas/markdown"),
  };

  // Prefer development mode if .pi/ exists
  if (fs.existsSync(paths.devExtDir) || fs.existsSync(paths.devSchemasSrc)) {
    return { ...paths, mode: "dev", extDir: paths.devExtDir, schemasSrc: paths.devSchemasSrc };
  }

  // Fall back to installed package mode
  if (fs.existsSync(paths.pkgExtDir) || fs.existsSync(paths.pkgSchemasSrc)) {
    return { ...paths, mode: "pkg", extDir: paths.pkgExtDir, schemasSrc: paths.pkgSchemasSrc };
  }

  // Neither found
  return { ...paths, mode: "none", extDir: null, schemasSrc: null };
}

// ── Tool: init_workspace (with jsonschema install) ──────────────────────────

function registerInitWorkspace(pi: ExtensionAPI) {
  pi.registerTool({
    name: "init_workspace",
    label: "Init Workspace",
    description:
      "Create the artifacts and tasks directory structure, copy " +
      "pre-create all artifact "
      "Markdown files with frontmatter, and install python dependencies. " +
      "Safe to run multiple times — skips existing files.",
    parameters: Type.Object({
      force: Type.Optional(Type.Boolean({
        description:
          "Overwrite existing skills and artifact files instead of skipping them.",
      })),
    }),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const cwd = ctx.cwd;
      const pkgPaths = resolvePackagePaths(cwd);
      const schemasSrc = pkgPaths.schemasSrc;

      // 1. Create directories
      const dirs = [
        path.resolve(cwd, "artifacts"),
        path.resolve(cwd, "tasks"),
        path.resolve(cwd, "tasks/epics"),
        path.resolve(cwd, "tasks/reviews"),
      ];
      for (const d of dirs) {
        fs.mkdirSync(d, { recursive: true });
      }

      // 2. Pre-create artifact files with frontmatter
      const artifactDefs: Array<{ name: string; file: string }> = [
        { name: "GoalSpec", file: "GoalSpec.md" },
        { name: "Glossary", file: "Glossary.md" },
        { name: "DesignSpec", file: "DesignSpec.md" },
        { name: "ArchitectureSpec", file: "ArchitectureSpec.md" },
        { name: "DataSpec", file: "DataSpec.md" },
        { name: "ApiSpec", file: "ApiSpec.md" },
        { name: "TestSpec", file: "TestSpec.md" },
      ];

      function extractSections(schemaPath: string): string[] {
        if (!fs.existsSync(schemaPath)) return [];
        const content = fs.readFileSync(schemaPath, "utf-8");
        const headingRegex = /^###\s+(.+)$/gm;
        const all: string[] = [];
        let m: RegExpExecArray | null;
        while ((m = headingRegex.exec(content)) !== null) {
          const name = m[1].trim();
          if (name.toLowerCase().includes("confirmation gate")) continue;
          if (/^Stage\s+\d/.test(name)) continue;
          all.push(name);
        }
        return all;
      }

      const created: string[] = [];
      const skippedArtifacts: string[] = [];

      if (fs.existsSync(schemasSrc)) {
        for (const def of artifactDefs) {
          const schemaPath = path.join(schemasSrc, def.file);
          const artifactPath = path.resolve(cwd, "artifacts", def.file);

          let artifactName = def.name;
          if (fs.existsSync(schemaPath)) {
            const schemaContent = fs.readFileSync(schemaPath, "utf-8");
            const nameMatch = schemaContent.match(/^---\nname:\s*(.+?)\n/m);
            if (nameMatch) {
              artifactName = nameMatch[1].trim();
            }
          }

          const pendingSections = extractSections(schemaPath);

          const fmLines: string[] = ["---"];
          fmLines.push(`artifact: ${artifactName}`);
          fmLines.push("status: in_progress");
          fmLines.push("sections_complete: []");
          if (pendingSections.length > 0) {
            fmLines.push("sections_pending:");
            for (const s of pendingSections) {
              fmLines.push(`  - ${s}`);
            }
          } else {
            fmLines.push("sections_pending: []");
          }
          fmLines.push("---");

          const fm = fmLines.join("\n") + "\n";

          if (fs.existsSync(artifactPath) && !_params.force) {
            skippedArtifacts.push(def.file);
          } else {
            fs.writeFileSync(artifactPath, fm, "utf-8");
            created.push(def.file);
          }
        }
      }

      // 4. Validate artifact filenames against expected naming convention
      const artifactsDir = path.resolve(cwd, 'artifacts');
      const expectedJsonNames = artifactDefs.map(d => `${d.file.replace('.md', '.json')}`);
      const expectedMdNames = artifactDefs.map(d => d.file);
      const mismatches: Array<{
        current: string;
        expected: string;
        reason: string;
      }> = [];

      if (fs.existsSync(artifactsDir)) {
        const existingJsonFiles = fs.readdirSync(artifactsDir)
          .filter(f => f.endsWith('.json') && !f.endsWith('.schema.json'));

        for (const jsonFile of existingJsonFiles) {
          // Check if this is a standard name
          if (expectedJsonNames.includes(jsonFile)) continue;

          // Check if a corresponding .md file exists with the standard name
          // e.g., Data.json → check if DataSpec.md exists in artifacts/
          const baseName = jsonFile.replace(/\.json$/, '');
          const mdWithSpec = baseName + 'Spec.md';
          const mdWithoutSpec = baseName + '.md';

          // Determine the actual .md file that exists
          const actualMd = expectedMdNames.includes(mdWithSpec) ? mdWithSpec
            : expectedMdNames.includes(mdWithoutSpec) ? mdWithoutSpec
            : null;

          if (actualMd) {
            // A corresponding .md file exists. The JSON should match the .md's name.
            const expectedJson = actualMd.replace('.md', '.json');
            if (expectedJsonNames.includes(expectedJson) && jsonFile !== expectedJson) {
              mismatches.push({
                current: jsonFile,
                expected: expectedJson,
                reason: `JSON uses "${baseName}" but corresponding "${actualMd}" expects "${expectedJson}"`,
              });
            }
          }
        }
      }

      // 5. Install python dependencies (prefer venv, fall back to system pip)
      let pipOutput = '';
      let pipSuccess = false;
      const venvPython = path.resolve(cwd, '.venv/bin/pip');
      const pipCmd = fs.existsSync(venvPython) ? venvPython : 'pip';
      try {
        const { stdout, stderr } = await execFilePromise(
          pipCmd, ['install', 'jsonschema'],
          { timeout: 30000, cwd },
        );
        pipOutput = stdout || stderr || '';
        pipSuccess = true;
      } catch {
        pipOutput = 'jsonschema installation failed — linting may not work without it.';
      }

      // 6. Rename mismatched files (non-standard → standard names)
      const renamed: Array<{ from: string; to: string }> = [];
      for (const m of mismatches) {
        const fromPath = path.join(artifactsDir, m.current);
        const toPath = path.join(artifactsDir, m.expected);
        fs.renameSync(fromPath, toPath);
        renamed.push({ from: m.current, to: m.expected });
      }

      // 7. Report
      const lines: string[] = [
        `Workspace initialized:`,
        ...dirs.map((d) => `  ✓ ${path.relative(cwd, d)}/`),
      ];

      if (created.length > 0) {
        lines.push(`  ✓ artifact files created: ${created.join(", ")}`);
      }
      if (skippedArtifacts.length > 0) {
        lines.push(`  • artifact files skipped (already exist): ${skippedArtifacts.join(", ")}`);
      }
      if (created.length === 0 && skippedArtifacts.length === 0) {
        lines.push(`  • artifact files already present — use force:true to overwrite`);
      }

      lines.push(`  ✓ python deps: jsonschema ${pipSuccess ? 'installed' : '⚠ install failed'}`);
      if (pipOutput) {
        const firstLine = pipOutput.split('\n')[0]?.trim();
        if (firstLine) lines.push(`    ${firstLine}`);
      }

      // Report filename mismatches
      if (renamed.length > 0) {
        lines.push(`  ✓ renamed ${renamed.length} file(s) to standard naming:`);
        for (const r of renamed) {
          lines.push(`    ${r.from} → ${r.expected}`);
        }
      } else if (mismatches.length > 0) {
        // Should not happen since we rename immediately, but keep for safety
        lines.push(`  ⚠ ${mismatches.length} filename mismatch(es) detected and auto-renamed`);
      }

      return {
        content: [{ type: "text", text: lines.join('\n') }],
        details: {
          dirs_created: dirs.filter((d) => fs.existsSync(d)),

          artifacts_created: created,
          artifacts_skipped: skippedArtifacts,
          pipSuccess,
          mismatches: mismatches.length > 0 ? mismatches : undefined,
          renamed,
        },
      };
    },
  });
}

// ── Tool: lint ───────────────────────────────────────────────────────────────

function registerLint(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "lint",
    label: "Lint",
    description:
      "Run the full SDLC spec linter suite. Checks all available " +
      "artifact JSON files for structural errors, cross-spec consistency, " +
      "and completeness gates. " +
      'mode: "assess" (default) — runs linter, interprets results, returns "block" or "proceed". ' +
      'mode: "raw" — returns raw JSON report.',
    parameters: Type.Object({
      artifacts: Type.Optional(
        Type.Array(Type.String(), {
          description:
            "Optional filter: only lint these artifact types. " +
            "e.g. ['goal', 'design', 'arch']. Without this, lints all available artifacts.",
        }),
      ),
      mode: Type.Optional(Type.String({
        description: 'Output mode: "assess" (default, decision-making) or "raw" (raw JSON report).',
        default: "assess",
      })),
      epic: Type.Optional(Type.String({
        description: 'Epic ID for issues lint (e.g., "EP-001").',
      })),
      epicsDir: Type.Optional(Type.String({
        description: 'Path to epics directory (default: "tasks/epics").',
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const linter = path.join(extDir, "linters/lint_all.py");
      const suiteFile = resolvePkgResource(extDir, 'skills/blueprint/schemas/json/suite.json');
      const mode = params.mode || "assess";

      if (!fs.existsSync(linter)) {
        return {
          content: [{ type: "text", text: `ERROR: linter not found at ${linter}` }],
          details: { verified: false },
          isError: true,
        };
      }

      try {
        const args = ["--json", "--suite", suiteFile];
        if (params.epic) {
          args.push("--epic", params.epic);
        }
        if (params.epicsDir) {
          args.push("--epics-dir", params.epicsDir);
        }
        if (params.artifacts && params.artifacts.length > 0) {
          const flagMap: Record<string, string> = {
            goal: "--goal",
            glossary: "--glossary",
            design: "--design",
            arch: "--arch",
            data: "--data",
            api: "--api",
            test: "--test",
          };
          for (const art of params.artifacts) {
            const flag = flagMap[art];
            if (flag) {
              const jsonPath = path.resolve(ctx.cwd, `artifacts/${art === "arch" ? "ArchitectureSpec" : art === "data" ? "DataSpec" : art === "api" ? "ApiSpec" : art === "design" ? "DesignSpec" : art === "glossary" ? "Glossary" : art === "test" ? "TestSpec" : "GoalSpec"}.json`);
              if (fs.existsSync(jsonPath)) {
                args.push(flag, jsonPath);
              }
            }
          }
        }

        const { stdout, stderr } = await execFilePromise("python", args, {
          cwd: ctx.cwd,
          timeout: 30000,
        });

        const result = JSON.parse(stdout);

        if (mode === "raw") {
          return {
            content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
            details: {
              clean: result.clean,
              totalErrors: result.totalErrors,
              totalWarnings: result.totalWarnings,
            },
          };
        }

        // mode === "assess" — interpret results and return decision
        const blockingErrors = result.layers
          ?.filter((l: any) => !l.skipped && l.errors?.length > 0)
          .flatMap((l: any) => l.errors)
          .map((e: any) => ({ category: e.category, message: e.message, hint: e.hint })) || [];

        const allWarnings = result.layers
          ?.filter((l: any) => !l.skipped && l.warnings?.length > 0)
          .flatMap((l: any) => l.warnings)
          .map((e: any) => ({ category: e.category, message: e.message, hint: e.hint })) || [];

        const completeness = result.completeness || [];
        const readyForReview = completeness.filter((s: any) => !s.readyForReview);
        const readyForConfirm = completeness.filter((s: any) => !s.readyForConfirm);

        let decision: "proceed" | "block";
        let message: string;

        if (blockingErrors.length > 0) {
          decision = "block";
          message = `Lint found ${blockingErrors.length} error(s) — must fix before proceeding:\n` +
            blockingErrors.slice(0, 10).map(e => `  ✗ [${e.category}] ${e.message}`).join('\n') +
            (blockingErrors.length > 10 ? `\n  ... and ${blockingErrors.length - 10} more` : '');
        } else if (allWarnings.length > 0 || readyForReview.length > 0) {
          decision = "proceed";
          message = `Lint passed. ${allWarnings.length} warning(s), ${readyForReview.length} completeness gate(s) pending review.`;
          if (allWarnings.length > 0) {
            message += '\nWarnings:\n' +
              allWarnings.slice(0, 5).map(e => `  ⚠ [${e.category}] ${e.message}`).join('\n') +
              (allWarnings.length > 5 ? '\n  ... and more' : '');
          }
        } else {
          decision = "proceed";
          message = `Lint clean — ${completeness.length} spec(s) checked.`;
        }

        return {
          content: [{ type: "text", text: message }],
          details: {
            decision,
            clean: result.clean,
            totalErrors: result.totalErrors,
            totalWarnings: result.totalWarnings,
            blockingErrors,
            warnings: allWarnings,
            completeness,
          },
        };
      } catch (err: any) {
        const message = err.stdout || err.stderr || err.message;
        return {
          content: [{ type: "text", text: `Lint failed:\n${message}` }],
          details: { verified: false },
          isError: true,
        };
      }
    },
  });
}

// ── Tool: update_frontmatter ─────────────────────────────────────────────────

function registerUpdateFrontmatter(pi: ExtensionAPI) {
  pi.registerTool({
    name: "update_frontmatter",
    label: "Update Frontmatter",
    description:
      "Update an artifact's frontmatter: status, sections_complete, " +
      "sections_pending. The 'updated' field is set automatically to " +
      "today's date. Preserves the artifact name from existing frontmatter.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Artifact file path (e.g. artifacts/GoalSpec.md)",
      }),
      status: Type.String({
        description: "New status: in_progress | needs_review | complete",
      }),
      sections_complete: Type.Array(Type.String(), {
        description: "List of confirmed section names.",
      }),
      sections_pending: Type.Array(Type.String(), {
        description: "List of pending section names.",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, status, sections_complete, sections_pending } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);

      if (!fs.existsSync(fullPath)) {
        return {
          content: [{ type: "text", text: `ERROR: file not found: ${filePath}` }],
          details: { verified: false, path: filePath },
          isError: true,
        };
      }

      const text = fs.readFileSync(fullPath, "utf-8");
      const updated = new Date().toISOString().slice(0, 10);

      const artifactMatch = text.match(/^---\nartifact:\s*(.+?)\n/m);
      const existingArtifact = artifactMatch?.[1].trim();

      const fmLines: string[] = ["---"];
      if (existingArtifact) {
        fmLines.push(`artifact: ${existingArtifact}`);
      }
      fmLines.push(`status: ${status}`);
      fmLines.push(`sections_complete:`);
      for (const s of sections_complete) {
        fmLines.push(`  - ${s}`);
      }
      fmLines.push(`sections_pending:`);
      for (const s of sections_pending) {
        fmLines.push(`  - ${s}`);
      }
      fmLines.push(`updated: ${updated}`);
      fmLines.push("---");

      const newFm = fmLines.join("\n") + "\n";
      const fmRegex = /^---\n[\s\S]*?\n---\n/;
      const body = text.replace(fmRegex, newFm);

      fs.writeFileSync(fullPath, body, "utf-8");

      const written = fs.readFileSync(fullPath, "utf-8");
      const hasStatus = written.includes(`status: ${status}`);
      const hasUpdated = written.includes(`updated: ${updated}`);

      if (!hasStatus || !hasUpdated) {
        return {
          content: [{ type: "text", text: `ERROR: frontmatter update verification failed for ${filePath}` }],
          details: { verified: false, path: filePath },
          isError: true,
        };
      }

      return {
        content: [{ type: "text", text: `Frontmatter updated: status=${status}, ${sections_complete.length} complete, ${sections_pending.length} pending` }],
        details: { verified: true, path: filePath, status, updated },
      };
    },
  });
}

// ── Tool: write_section ──────────────────────────────────────────────────────

function registerWriteSection(pi: ExtensionAPI) {
  pi.registerTool({
    name: "write_section",
    label: "Write Section",
    description:
      "Write a confirmed artifact section to disk and update frontmatter " +
      "in one operation. First section creates the file; subsequent " +
      "sections append. Frontmatter is updated with status=in_progress. " +
      "If jsonContent is provided, also writes/updates the parallel JSON " +
      "artifact file (the complete JSON for the entire artifact).",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Output file path (e.g. artifacts/GoalSpec.md)",
      }),
      section: Type.String({
        description: "Section name (e.g. Project Objective, Non-Goals)",
      }),
      content: Type.String({
        description: "The validated section content to write.",
      }),
      sections_complete: Type.Array(Type.String(), {
        description: "List of confirmed section names (including the one just written).",
      }),
      sections_pending: Type.Array(Type.String(), {
        description: "List of section names still to be confirmed.",
      }),
      jsonContent: Type.Optional(Type.Object({}, {
        description: "Complete JSON object for the entire artifact. Written to the parallel .json file. The blueprint skill accumulates this across sections.",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, section, content, sections_complete, sections_pending, jsonContent } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const dir = path.dirname(fullPath);
      const updated = new Date().toISOString().slice(0, 10);

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // ── Write markdown section ───────────────────────────────────────────
      const separator = "---\n";

      if (!fs.existsSync(fullPath)) {
        const fmLines: string[] = [separator];
        fmLines.push("status: in_progress");
        fmLines.push("sections_complete:");
        for (const s of sections_complete) {
          fmLines.push(`  - ${s}`);
        }
        fmLines.push("sections_pending:");
        for (const s of sections_pending) {
          fmLines.push(`  - ${s}`);
        }
        fmLines.push(`updated: ${updated}`);
        fmLines.push("---");

        const body = [...fmLines, "\n", content].join("");
        fs.writeFileSync(fullPath, body, "utf-8");
      } else {
        fs.appendFileSync(fullPath, "\n\n" + content, "utf-8");
      }

      // Update frontmatter
      const fmLinesNew: string[] = ["---"];
      const existingText = fs.readFileSync(fullPath, "utf-8");
      const artifactMatch = existingText.match(/^---\nartifact:\s*(.+?)\n/m);
      if (artifactMatch) {
        fmLinesNew.push(`artifact: ${artifactMatch[1].trim()}`);
      }
      fmLinesNew.push("status: in_progress");
      fmLinesNew.push("sections_complete:");
      for (const s of sections_complete) {
        fmLinesNew.push(`  - ${s}`);
      }
      fmLinesNew.push("sections_pending:");
      for (const s of sections_pending) {
        fmLinesNew.push(`  - ${s}`);
      }
      fmLinesNew.push(`updated: ${updated}`);
      fmLinesNew.push("---");

      const newFm = fmLinesNew.join("\n") + "\n";
      const fmRegex = /^---\n[\s\S]*?\n---\n/;
      const body = existingText.replace(fmRegex, newFm);

      fs.writeFileSync(fullPath, body, "utf-8");

      // ── Write JSON content (if provided) ─────────────────────────────────
      let jsonPath: string | null = null;
      let jsonWritten = false;
      if (jsonContent) {
        jsonPath = fullPath.replace(/\.md$/, '.json');
        fs.writeFileSync(jsonPath, JSON.stringify(jsonContent, null, 2) + '\n');
        jsonWritten = true;
      }

      // ── Verify markdown ──────────────────────────────────────────────────
      const written = fs.readFileSync(fullPath, "utf-8");
      const hasSection = written.includes(section);
      const hasContent = written.includes(content.slice(0, 50));
      const hasStatus = written.includes("status: in_progress");
      const hasUpdated = written.includes(`updated: ${updated}`);

      if (!hasSection || !hasContent || !hasStatus || !hasUpdated) {
        return {
          content: [{ type: "text", text: `ERROR: write-section verification failed for ${filePath}` }],
          details: { verified: false, path: filePath },
          isError: true,
        };
      }

      const jsonInfo = jsonWritten
        ? `\n  JSON: ${jsonPath} written (${Object.keys(jsonContent).length} keys)`
        : '';

      return {
        content: [{
          type: "text",
          text: `Section "${section}" written to ${filePath}. Frontmatter updated. Verified.${jsonInfo}`,
        }],
        details: {
          verified: true,
          path: filePath,
          section,
          status: "in_progress",
          updated,
          jsonWritten,
          jsonPath: jsonPath || undefined,
        },
      };
    },
  });
}

// ── Tool: generate_tests ─────────────────────────────────────────────────────

function registerGenerateTests(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "generate_tests",
    label: "Generate Tests",
    description:
      "Generate TestSpec test cases for all ApiSpec functions that don't have tests yet. " +
      "Reads GoalSpec for REQ/NFR traceability. Produces structured test entries with " +
      "happy-path, edge-case, and error-path categories. Writes directly to TestSpec.json.",
    parameters: Type.Object({
      apiSpecPath: Type.Optional(Type.String({
        description: "Path to ApiSpec JSON. Default: artifacts/Api.json",
      })),
      goalSpecPath: Type.Optional(Type.String({
        description: "Path to GoalSpec JSON for REQ/NFR traceability. Default: artifacts/GoalSpec.json",
      })),
      testSpecPath: Type.Optional(Type.String({
        description: "Path to existing TestSpec JSON. Default: artifacts/Test.json",
      })),
      reqMappingPath: Type.Optional(Type.String({
        description: "Path to REQ→Fn mapping JSON. Default: artifacts/req_fn_mapping.json",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const script = path.join(extDir, "scripts/generate_tests.py");

      if (!fs.existsSync(script)) {
        return {
          content: [{ type: "text", text: `ERROR: generate_tests.py not found at ${script}` }],
          details: { success: false },
          isError: true,
        };
      }

      const args: string[] = [];
      const defaults = {
        api: "artifacts/ApiSpec.json",
        goal: "artifacts/GoalSpec.json",
        test: "artifacts/TestSpec.json",
        mapping: "artifacts/req_fn_mapping.json",
      };

      const apiPath = params.apiSpecPath || path.resolve(ctx.cwd, defaults.api);
      const goalPath = params.goalSpecPath ? path.resolve(ctx.cwd, params.goalSpecPath) : undefined;
      const testPath = params.testSpecPath ? path.resolve(ctx.cwd, params.testSpecPath) : undefined;
      const mappingPath = params.reqMappingPath ? path.resolve(ctx.cwd, params.reqMappingPath) : undefined;

      if (!fs.existsSync(apiPath)) {
        return {
          content: [{ type: "text", text: `ERROR: ApiSpec not found at ${apiPath}` }],
          details: { success: false },
          isError: true,
        };
      }
      args.push(apiPath);
      if (goalPath && fs.existsSync(goalPath)) args.push(goalPath);
      if (testPath) args.push(testPath);
      if (mappingPath && fs.existsSync(mappingPath)) args.push(mappingPath);

      try {
        const { stdout, stderr } = await execFilePromise("python", [script, ...args], {
          cwd: ctx.cwd,
          timeout: 30000,
        });
        return {
          content: [{ type: "text", text: stdout.trim() }],
          details: { success: true, output: stdout.trim(), stderr: stderr.trim() },
        };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `generate_tests failed:\n${err.stderr || err.message}` }],
          details: { success: false, error: err.stderr || err.message },
          isError: true,
        };
      }
    },
  });
}

// ── Tool: generate_diagrams ──────────────────────────────────────────────────

function registerGenerateDiagrams(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "generate_diagrams",
    label: "Generate Diagrams",
    description:
      "Generate data model diagrams in multiple formats from DataSpec JSON. " +
      "Supports PlantUML, Mermaid, draw.io, DBML, and D2. " +
      "Outputs to a configurable directory (default: diagrams/).",
    parameters: Type.Object({
      dataSpecPath: Type.Optional(Type.String({
        description: "Path to DataSpec JSON. Default: artifacts/Data.json",
      })),
      formats: Type.Optional(Type.String({
        description: "Comma-separated formats: puml,mermaid,drawio,dbml,d2 (default: all)",
      })),
      outputDir: Type.Optional(Type.String({
        description: "Output directory relative to project root. Default: diagrams",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const script = path.join(extDir, "scripts/json_uml_convert.py");

      if (!fs.existsSync(script)) {
        return {
          content: [{ type: "text", text: `ERROR: json_uml_convert.py not found at ${script}` }],
          details: { success: false },
          isError: true,
        };
      }

      const dataPath = params.dataSpecPath || path.resolve(ctx.cwd, "artifacts/DataSpec.json");
      const formats = params.formats || "all";
      const outputDir = params.outputDir || "diagrams";

      if (!fs.existsSync(dataPath)) {
        return {
          content: [{ type: "text", text: `ERROR: DataSpec not found at ${dataPath}` }],
          details: { success: false },
          isError: true,
        };
      }

      // Create output directory
      const outPath = path.resolve(ctx.cwd, outputDir);
      fs.mkdirSync(outPath, { recursive: true });

      try {
        const { stdout, stderr } = await execFilePromise("python", [script, dataPath, formats, outPath], {
          cwd: ctx.cwd,
          timeout: 30000,
        });
        const lines = stdout.trim().split("\n");
        const generatedFiles = lines.filter(l => l.includes("✓")).map(l => l.match(/✓\s+(.+?)\s+\(/)?.[1] || l);

        // Verify output files actually exist
        const missing = generatedFiles.filter(f => !fs.existsSync(path.join(outPath, f)));
        if (missing.length > 0) {
          return {
            content: [{
              type: "text",
              text: `generate_diagrams reported success but ${missing.length} file(s) not found:\n` +
                missing.map(f => `  ✗ ${f}`).join("\n") +
                `\n\nCheck the script output below for errors.`,
            }],
            details: {
              success: false,
              output: stdout.trim(),
              stderr: stderr.trim(),
              outputDir: outputDir,
              generatedFiles,
              missingFiles: missing,
            },
            isError: true,
          };
        }

        return {
          content: [{ type: "text", text: stdout.trim() }],
          details: {
            success: true,
            output: stdout.trim(),
            stderr: stderr.trim(),
            outputDir: outputDir,
            generatedFiles,
          },
        };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `generate_diagrams failed:\n${err.stderr || err.message}` }],
          details: { success: false, error: err.stderr || err.message },
          isError: true,
        };
      }
    },
  });
}

// ── Schema path resolution ──────────────────────────────────────────────────
// Schemas live at skills/blueprint/schemas/json/ relative to the package root.
// extDir points to extensions/blueprint/ relative to the package root.
// We need a helper that resolves from extDir to the schemas directory.

function resolveSchemaPath(extDir: string, schemaName: string): string {
  const packageRoot = path.join(extDir, '..', '..');
  return path.join(packageRoot, 'skills', 'blueprint', 'schemas', 'json', `${schemaName}.schema.json`);
}

// Resolve any resource path relative to the package root (sibling of extensions/)
function resolvePkgResource(extDir: string, relPath: string): string {
  const packageRoot = path.join(extDir, '..', '..');
  return path.join(packageRoot, relPath);
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function (pi: ExtensionAPI) {
  // Resolve extDir relative to this file's location
  // Works both in development (.pi/extensions/blueprint/) and when installed as package (extensions/blueprint/)
  const extDir = path.resolve(__dirname);

  registerInitWorkspace(pi);
  registerLoadArtifact(pi);
  registerLint(pi, extDir);
  registerUpdateFrontmatter(pi);
  registerWriteSection(pi);
  registerDualOutput(pi, extDir);
  registerHandoff(pi);
  registerGenerateTests(pi, extDir);
  registerGenerateDiagrams(pi, extDir);
}
