import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import path from "node:path";
import { resolvePkgResource } from "../utils";

export function registerGenerateArtifactMarkdown(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "generate_artifact_markdown",
    label: "Generate Artifact Markdown",
    description:
      "Convert an artifact JSON file to Markdown format. Reads the JSON " +
      "and generates the corresponding .md file using schema-aware formatting.",
    parameters: Type.Object({
      artifactType: Type.String({
        description: "Artifact type: goal, glossary, design, arch, data, api, test, plan, issue",
      }),
      jsonPath: Type.String({
        description: "Path to the JSON artifact file (e.g. artifacts/GoalSpec.json)",
      }),
      outputPath: Type.String({
        description: "Output markdown path (default: artifacts/<Type>.md)",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { artifactType, jsonPath, outputPath } = params;
      const jsonFullPath = path.resolve(ctx.cwd, jsonPath);
      const outPath = outputPath ? path.resolve(ctx.cwd, outputPath) : undefined;

      const cmd = [
        process.execPath,
        resolvePkgResource(extDir, "extensions/blueprint/generate_artifact_markdown.py"),
        "--type", artifactType,
        "--json", jsonFullPath,
        ...(outPath ? ["--output", outPath] : []),
      ].join(" ");

      try {
        const { stdout, stderr } = await ctx.sh(cmd);
        return {
          content: [{ type: "text", text: stdout.trim() }],
          details: { success: true },
        };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `generate_artifact_markdown failed:\n${stderr || err.message}` }],
          details: { success: false, error: stderr || err.message },
          isError: true,
        };
      }
    },
  });
}
