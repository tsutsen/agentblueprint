import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { DEPS, resolvePackagePaths } from "../utils";

export function registerLoadArtifact(pi: ExtensionAPI) {
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
