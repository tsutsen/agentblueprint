import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise, resolvePkgResource, resolvePython } from "../utils";

export function registerLint(pi: ExtensionAPI, extDir: string) {
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
      artifacts: Type.Optional(Type.Array(Type.String(), {
        description: "Optional filter: only lint these artifact types. " +
          "Valid values: goal, glossary, design, arch, data, api, test. " +
          "e.g. ['goal', 'design', 'arch']. Without this, lints all available artifacts.",
      })),
      mode: Type.Optional(Type.Enum({ assess: "assess", raw: "raw" }, {
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
      const suiteFile = resolvePkgResource(extDir, 'skills/blueprint/schemas/suite.json');
      const mode = params.mode || "assess";

      if (!fs.existsSync(linter)) {
        return {
          content: [{ type: "text", text: `ERROR: linter not found at ${linter}` }],
          details: { verified: false },
          isError: true,
        };
      }

      try {
        const jsonNames: Record<string, string> = {
          goal: "GoalSpec.json", glossary: "Glossary.json",
          design: "DesignSpec.json", arch: "ArchitectureSpec.json",
          data: "DataSpec.json", api: "ApiSpec.json", test: "TestSpec.json",
        };
        const flagMap: Record<string, string> = {
          goal: "--goal", glossary: "--glossary", design: "--design",
          arch: "--arch", data: "--data", api: "--api", test: "--test",
        };

        const actualArtifacts = Object.entries(jsonNames).filter(([_, name]) =>
          fs.existsSync(path.resolve(ctx.cwd, "artifacts", name))
        );

        const lintersDir = path.resolve(extDir, "linters");
        const schemasDir = resolvePkgResource(extDir, 'skills/blueprint/schemas');

        let args: string[];
        if (actualArtifacts.length > 0) {
          args = [linter, "--json", "--linters", lintersDir, "--schemas", schemasDir];
          if (params.epic) args.push("--epic", params.epic);
          if (params.epicsDir) args.push("--epics-dir", params.epicsDir);

          if (params.artifacts && params.artifacts.length > 0) {
            for (const art of params.artifacts) {
              const f = flagMap[art];
              if (f) {
                const jsonPath = path.resolve(ctx.cwd, "artifacts", jsonNames[art]);
                if (fs.existsSync(jsonPath)) args.push(f, jsonPath);
              }
            }
          } else {
            for (const [key, name] of actualArtifacts) {
              if (flagMap[key]) {
                args.push(flagMap[key], path.resolve(ctx.cwd, "artifacts", name));
              }
            }
          }
        } else {
          args = [linter, "--json", "--suite", suiteFile, "--linters", lintersDir, "--schemas", schemasDir];
          if (params.epic) args.push("--epic", params.epic);
          if (params.epicsDir) args.push("--epics-dir", params.epicsDir);
        }

        const { stdout, stderr } = await execFilePromise(resolvePython(ctx.cwd), args, {
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

        // Truncate details to avoid flooding the conversation
        const summaryErrors = blockingErrors.slice(0, 3).map(e => ({
          category: e.category, message: e.message, hint: e.hint,
        }));
        const summaryWarnings = allWarnings.slice(0, 3).map(e => ({
          category: e.category, message: e.message, hint: e.hint,
        }));
        const summaryCompleteness = completeness.slice(0, 3).map(c => ({
          name: c.name, readyForReview: c.readyForReview, readyForConfirm: c.readyForConfirm,
        }));

        return {
          content: [{ type: "text", text: message }],
          details: {
            decision,
            clean: result.clean,
            totalErrors: result.totalErrors,
            totalWarnings: result.totalWarnings,
            blockingErrors: summaryErrors,
            warnings: summaryWarnings,
            completeness: summaryCompleteness,
            // Full counts for reference
            _blockingErrorsTotal: blockingErrors.length,
            _warningsTotal: allWarnings.length,
            _completenessTotal: completeness.length,
          },
        };
      } catch (err: any) {
        const message = err.stderr || err.stdout || err.message;
        return {
          content: [{ type: "text", text: `Lint failed:\n${message}` }],
          details: { verified: false },
          isError: true,
        };
      }
    },
  });
}
