import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise } from "../utils";

export function registerGraphMetrics(pi: ExtensionAPI, extDir: string) {
  const script = path.join(extDir, "scripts", "graph_metrics.py");

  async function runMetrics(artifacts: string, format: string, reportPath: string | null = null) {
    if (!fs.existsSync(script)) {
      return {
        content: [{ type: "text", text: `ERROR: graph_metrics.py not found at ${script}` }],
        details: { success: false },
        isError: true,
      };
    }

    const args = ["--artifacts", artifacts, "--format", format];
    if (reportPath) args.push("--report", reportPath);

    try {
      const { stdout, stderr } = await execFilePromise("python3", [script, ...args], {
        cwd: extDir,
        timeout: 60000,
      });
      return {
        content: [{ type: "text", text: stdout.trim() }],
        details: { success: true, output: stdout.trim(), stderr: stderr.trim() },
      };
    } catch (err: any) {
      const msg = err.stdout || err.stderr || err.message;
      return {
        content: [{ type: "text", text: `graph_metrics failed:\n${msg}` }],
        details: { success: false, error: err.stderr || err.message },
        isError: true,
      };
    }
  }

  // Full metrics report
  pi.registerTool({
    name: "graph-metrics",
    label: "Graph Metrics",
    description:
      "Run full architecture graph metrics analysis. Builds a unified graph from all " +
      "artifact JSON files and computes 10 quality metrics: health index, traceability, " +
      "orphan detection, blast radius, risk scores, component load, interface pressure, " +
      "test density, epic coherence, and layer violations. Returns a detailed report.",
    parameters: Type.Object({
      artifacts: Type.Optional(Type.String({
        description: "Path to artifacts directory. Default: artifacts",
      })),
      format: Type.Optional(Type.String({
        description: 'Output format: "text" (default) or "json"',
      })),
      reportPath: Type.Optional(Type.String({
        description: "Path to write report file. Default: stdout",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const artifacts = params.artifacts || path.resolve(ctx.cwd, "artifacts");
      const format = params.format || "text";
      const reportPath = params.reportPath || null;
      return runMetrics(artifacts, format, reportPath);
    },
  });

  // Fast lint: orphan + layer violation checks only
  pi.registerTool({
    name: "graph-lint",
    label: "Graph Lint",
    description:
      "Fast graph linting: checks for orphaned nodes (ERROR severity) and " +
      "layer violations. Suitable for CI pipelines. Exits with code 1 if errors found.",
    parameters: Type.Object({
      artifacts: Type.Optional(Type.String({
        description: "Path to artifacts directory. Default: artifacts",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const artifacts = params.artifacts || path.resolve(ctx.cwd, "artifacts");
      const result = await runMetrics(artifacts, "json");
      try {
        const data = JSON.parse(result.content[0].text);
        const errors: string[] = [];
        const orphans = data.orphans || {};
        for (const [class_name, nodes] of Object.entries(orphans)) {
          if (class_name === "orphan_req" || class_name === "orphan_con") {
            for (const nid of (nodes as string[])) {
              errors.push(`ERROR: ${class_name} ${nid}`);
            }
          }
        }
        const lv = data.layer_violations || [];
        for (const v of lv) {
          errors.push(`ERROR: layer_violation ${v.from} → ${v.to} (${v.from_type} → ${v.to_type})`);
        }
        if (errors.length > 0) {
          return {
            content: [{ type: "text", text: `Graph lint found ${errors.length} error(s):\n` + errors.slice(0, 20).join("\n") }],
            details: { success: false, errors },
            isError: true,
          };
        }
        return {
          content: [{ type: "text", text: "Graph lint clean — no errors found." }],
          details: { success: true },
        };
      } catch {
        return {
          content: [{ type: "text", text: `Failed to parse metrics output: ${result.content[0].text.substring(0, 200)}` }],
          details: { success: false },
          isError: true,
        };
      }
    },
  });
}
