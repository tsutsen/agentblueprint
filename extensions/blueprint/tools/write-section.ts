import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

export function registerWriteSection(pi: ExtensionAPI) {
  pi.registerTool({
    name: "write_section",
    label: "Write Section",
    description:
      "Write a confirmed artifact section to JSON during the interview. " +
      "The JSON is the single source of truth — Markdown is derived later " +
      "via generate_artifact_markdown. Records when the JSON is ready for " +
      "markdown generation with a `ready` flag and `readyAt` timestamp.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Output file path (e.g. artifacts/GoalSpec.json)",
      }),
      section: Type.String({
        description: "Section name (e.g. Project Objective, Non-Goals)",
      }),
      content: Type.String({
        description: "The validated section content to write.",
      }),
      jsonContent: Type.Optional(Type.Object({}, {
        description: "Complete JSON object for the entire artifact. Written to the .json file. The blueprint skill accumulates this across sections.",
      })),
      ready: Type.Optional(Type.Boolean({
        description: "Whether the JSON is ready for markdown generation. Set true when all sections are complete.",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, section, content, jsonContent, ready } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const dir = path.dirname(fullPath);
      const now = new Date().toISOString();

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      let jsonPath: string | null = null;
      let jsonWritten = false;
      if (jsonContent) {
        jsonPath = fullPath.replace(/\.md$/, '.json');
        if (ready) {
          jsonContent.ready = true;
          jsonContent.readyAt = now;
        }
        fs.writeFileSync(jsonPath, JSON.stringify(jsonContent, null, 2) + '\n');
        jsonWritten = true;
      }

      if (!jsonWritten) {
        return {
          content: [{ type: "text", text: `ERROR: write_section requires jsonContent. The JSON is the single source of truth; Markdown is derived later.` }],
          details: { success: false },
          isError: true,
        };
      }

      const written = fs.readFileSync(jsonPath, "utf-8");
      const revalidated = JSON.parse(written);

      return {
        content: [{
          type: "text",
          text: `Section written: ${section}\n` +
            `  JSON: ${jsonPath}\n` +
            `  Ready: ${revalidated.ready === true}`,
        }],
        details: { success: true, section, jsonPath, ready: revalidated.ready },
      };
    },
  });
}
