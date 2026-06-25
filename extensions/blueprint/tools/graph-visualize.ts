import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise } from "../utils";

export function registerGraphVisualize(pi: ExtensionAPI, extDir: string) {
  const script = path.join(extDir, "scripts", "graph-visualize.py");

  pi.registerTool({
    name: "graph-visualize",
    label: "Glossary Graph",
    description:
      "Generate an interactive force-directed graph visualization of glossary term " +
      "relationships and cross-specification references. Reads all spec JSON files from " +
      "the artifacts directory, extracts glossaryRefs, and builds a graph with term " +
      "connections, spec references, and cross-spec shared references. Opens in browser.",
    parameters: Type.Object({
      artifacts: Type.Optional(Type.String({
        description: "Path to artifacts directory. Default: artifacts",
      })),
      port: Type.Optional(Type.Number({
        description: "HTTP server port (default: 3001)",
      })),
      noServer: Type.Optional(Type.Boolean({
        description: "Only generate graph-data.json without starting server",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      if (!fs.existsSync(script)) {
        return {
          content: [{ type: "text", text: `ERROR: graph-visualize.py not found at ${script}` }],
          details: { success: false },
          isError: true,
        };
      }

      const artifacts = params.artifacts || path.resolve(ctx.cwd, "artifacts");
      const port = params.port || 3001;
      const noServer = !!params.noServer;

      const args = [script, artifacts, "--port", String(port)];
      if (noServer) args.push("--no-server");

      try {
        const { stdout, stderr } = await execFilePromise("python3", args, {
          cwd: ctx.cwd,
          timeout: 60000,
        });
        return {
          content: [{ type: "text", text: stdout.trim() }],
          details: { success: true, output: stdout.trim(), stderr: stderr.trim() },
        };
      } catch (err: any) {
        const msg = err.stdout || err.stderr || err.message;
        return {
          content: [{ type: "text", text: `graph-visualize failed:\n${msg}` }],
          details: { success: false, error: err.stderr || err.message },
          isError: true,
        };
      }
    },
  });
}
