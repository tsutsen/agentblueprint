import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise, resolvePython } from "../utils";

export function registerGraphTools(pi: ExtensionAPI, extDir: string) {
  const metricsScript = path.join(extDir, "scripts", "graph_metrics.py");
  const visualizeScript = path.join(extDir, "scripts", "graph-visualize.py");

  // ─── graph-metrics ─────────────────────────────────────────────────────────

  async function runMetrics(artifacts: string, format: string, reportPath: string | null = null) {
    if (!fs.existsSync(metricsScript)) {
      return {
        content: [{ type: "text", text: `ERROR: graph_metrics.py not found at ${metricsScript}` }],
        details: { success: false },
        isError: true,
      };
    }

    const args = ["--artifacts", artifacts, "--format", format];
    if (reportPath) args.push("--report", reportPath);

    try {
      const { stdout, stderr } = await execFilePromise(resolvePython(extDir), [metricsScript, ...args], {
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

      // For text format, truncate to show only key metrics
      if (format === "text") {
        const result = await runMetrics(artifacts, "json", reportPath);
        if (result.isError) return result;

        try {
          const data = JSON.parse(result.content[0].text);
          const health = data.health_index || {};
          const breakdown = health.breakdown || {};
          const orphans = data.orphans || {};
          const totalOrphans = Object.values(orphans).reduce((s: number, a: any) => s + a.length, 0);

          // Build concise summary
          const lines = [
            `Health Index: ${health.score || 'N/A'} / 100`,
            `  Coverage      ${breakdown.coverage ?? 'N/A'}`,
            `  Verifiability ${breakdown.verifiability ?? 'N/A'}`,
            `  Traceability  ${breakdown.traceability ?? 'N/A'}`,
            `  Orphan Rate   ${breakdown.orphan_rate ?? 'N/A'} (${totalOrphans} orphans)`,
            `  Layer OK      ${breakdown.layer_ok ?? 'N/A'}`,
          ];

          // Add traceability detail if available
          if (data.traceability?.per_req) {
            const full = Object.values(data.traceability.per_req).filter((r: any) => r.score === r.max).length;
            const total = data.traceability.total || 0;
            lines.push(`  Traceability: ${full}/${total} REQs fully traced`);
          }

          // Add layer violations count
          if (data.layer_violations?.length) {
            lines.push(`  Layer Violations: ${data.layer_violations.length}`);
          }

          return {
            content: [{ type: "text", text: lines.join('\n') }],
            details: {
              success: true,
              fullReport: data,
              health,
              orphans,
              traceability: data.traceability,
              layerViolations: data.layer_violations,
            },
          };
        } catch {
          // Fallback to raw output if JSON parse fails
          return runMetrics(artifacts, format, reportPath);
        }
      }

      return runMetrics(artifacts, format, reportPath);
    },
  });

  // ─── graph-lint ────────────────────────────────────────────────────────────

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

  // ─── graph-visualize ───────────────────────────────────────────────────────

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
      if (!fs.existsSync(visualizeScript)) {
        return {
          content: [{ type: "text", text: `ERROR: graph-visualize.py not found at ${visualizeScript}` }],
          details: { success: false },
          isError: true,
        };
      }

      const artifacts = params.artifacts || path.resolve(ctx.cwd, "artifacts");
      const port = params.port || 3001;
      const noServer = !!params.noServer;

      const args = [visualizeScript, artifacts, "--port", String(port)];
      if (noServer) args.push("--no-server");

      try {
        const { stdout, stderr } = await execFilePromise(resolvePython(ctx.cwd), args, {
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
