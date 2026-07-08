import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise, resolvePython } from "../utils";

export function registerGenerateDiagrams(pi: ExtensionAPI, extDir: string) {
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

      const outPath = path.resolve(ctx.cwd, outputDir);
      fs.mkdirSync(outPath, { recursive: true });

      try {
        const { stdout, stderr } = await execFilePromise(resolvePython(ctx.cwd), [script, dataPath, formats, outPath], {
          cwd: ctx.cwd,
          timeout: 30000,
        });
        const lines = stdout.trim().split("\n");
        const generatedFiles = lines.filter(l => l.includes("✓")).map(l => {
          const match = l.match(/✓\s+(.+?)\s+\(/);
          const fullPath = match?.[1] || l;
          return path.basename(fullPath);
        });

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
